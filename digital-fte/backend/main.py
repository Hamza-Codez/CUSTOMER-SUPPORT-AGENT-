"""FastAPI server for the Digital FTE Customer Support Agent.

Endpoints:
    POST /chat         -> send a message, get the agent's reply   (authenticated)
    POST /chat/stream  -> the same conversation as SSE            (authenticated)
    GET  /tickets      -> the audit log, for the dashboard        (role: agent)
    GET  /health       -> liveness check                          (open)

PRD v2 metric: 100% of state-changing endpoints require a valid session.
`/health` is the only unauthenticated route — it changes nothing and exposes
nothing but which providers are live.
"""
from __future__ import annotations

import json
import logging
import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import (AIMessage, AIMessageChunk, HumanMessage,
                                     messages_from_dict, messages_to_dict)
from pydantic import BaseModel

import config  # noqa: F401  — loads .env before any os.getenv below
import auth
import context
import store
from agent import get_agent
from auth import User, current_user, require_agent

logger = logging.getLogger("digital-fte")

app = FastAPI(title="Digital FTE — Customer Support Agent")

# Open in dev so the app runs with zero setup; set ALLOWED_ORIGINS to your
# frontend URL in production (comma-separated) so a session token can't be
# used from any other site.
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _announce_providers():
    """Say plainly which providers are live.

    A mock provider must never be mistaken for the real thing: the mock model is
    keyword routing, not reasoning, and the mock store forgets everything on
    restart. If any of these are on, the log says so on every boot.
    """
    live = {
        "model": os.getenv("MODEL_PROVIDER", "mock"),
        "data": store.backend_name(),
        "auth": auth.provider_name(),
        "embeddings": os.getenv("EMBEDDING_PROVIDER", "mock"),
    }
    mocked = [name for name, value in live.items() if value == "mock"]
    summary = " · ".join(f"{k}={v}" for k, v in live.items())

    if not mocked:
        logger.warning("PRODUCTION providers: %s", summary)
        return

    logger.warning("=" * 68)
    logger.warning(" NOT PRODUCTION — %s", summary)
    logger.warning(" Mocked: %s", ", ".join(mocked))
    if "model" in mocked:
        logger.warning(" The mock model matches keywords; it does not reason.")
        logger.warning("   -> MODEL_PROVIDER=ollama  (free: ollama pull llama3.1)")
        logger.warning("   -> MODEL_PROVIDER=openai  (needs OPENAI_API_KEY)")
    if "data" in mocked:
        logger.warning(" The mock store loses every ticket on restart.")
        logger.warning("   -> python scripts/apply_schema.py, then DATA_BACKEND=supabase")
    logger.warning("=" * 68)


@app.exception_handler(store.StoreUnavailable)
def _store_unavailable(request: Request, exc: store.StoreUnavailable):
    """503, not 500: the app is fine, its database isn't reachable or set up.

    The message is actionable (which migrations to run) because the most common
    cause is a fresh project with DATA_BACKEND=supabase and no schema yet.
    """
    logger.error("Data layer unavailable on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": str(exc)})

def _session_key(user: User, session_id: str) -> str:
    """Memory is scoped per user (INTENT §5): two people using the same
    `session_id` must never see each other's conversation. Composed here rather
    than in the store, so the session contracts stay unchanged."""
    return f"{user.id}:{session_id}"


def _load_history(user: User, session_id: str) -> list:
    """Session memory lives in the data layer; this converts it to LangChain
    messages. The store holds plain JSON dicts and never imports LangChain."""
    return messages_from_dict(store.get_session(_session_key(user, session_id)))


def _save_history(user: User, session_id: str, messages: list) -> None:
    store.save_session(_session_key(user, session_id), messages_to_dict(messages))


def _last_ai_text(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content.strip():
            return m.content
    return ""


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    provider: str


@app.get("/health")
def health():
    # `data` matters now that two stores exist: it tells you at a glance whether
    # the tickets you're looking at are in memory or in Postgres.
    return {
        "status": "ok",
        "provider": os.getenv("MODEL_PROVIDER", "mock"),
        "data": store.backend_name(),
        "auth": auth.provider_name(),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: User = Depends(current_user)):
    history = _load_history(user, req.session_id)
    history.append(HumanMessage(content=req.message))

    # The tools read the caller's identity from here — their signatures are
    # frozen by SPEC §5, so it cannot be passed as an argument.
    token = context.set_user_id(user.id)
    try:
        result = get_agent().invoke({"messages": history})
    except Exception as exc:  # never leak a stack trace to the customer
        # History is not saved, so a retry starts from clean memory.
        logger.exception("Agent invocation failed for session %s", req.session_id)
        raise HTTPException(
            status_code=500,
            detail=f"The support agent is temporarily unavailable ({type(exc).__name__}).",
        ) from exc
    finally:
        context.reset(token)

    # The agent returns the full message list; keep it as the new memory.
    _save_history(user, req.session_id, result["messages"])

    return ChatResponse(
        reply=_last_ai_text(result["messages"]) or "(no response)",
        session_id=req.session_id,
        provider=os.getenv("MODEL_PROVIDER", "mock"),
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, user: User = Depends(current_user)):
    """Same conversation as /chat, delivered as Server-Sent Events.

    Frames: {"type": "tool", "name": ...} when a tool starts,
            {"type": "token", "text": ...} for each text delta,
            {"type": "done", "reply": ..., "session_id": ...} once,
            {"type": "error", "detail": ...} if the agent fails.

    Errors arrive as a frame, not an HTTP status: by the time the agent fails
    the response has already started streaming and the status line is long gone.
    """
    history = _load_history(user, req.session_id)
    history.append(HumanMessage(content=req.message))

    async def events():
        final_messages = list(history)
        seen_tools: set[str] = set()
        # Set inside the generator, not around it: the body runs after the
        # handler has returned, in a fresh context where an outer token
        # would already have been reset.
        token = context.set_user_id(user.id)
        try:
            async for mode, payload in get_agent().astream(
                {"messages": history}, stream_mode=["messages", "values"]
            ):
                if mode == "values":
                    final_messages = payload["messages"]
                    continue

                chunk, _meta = payload
                # `messages` mode also yields ToolMessages — the raw tool output.
                # Only AI chunks are customer-facing text; streaming a tool result
                # would leak internal markers like "[Refund policy]" into the chat.
                if not isinstance(chunk, AIMessageChunk):
                    continue

                for call in chunk.tool_call_chunks or []:
                    name = call.get("name")
                    if name and name not in seen_tools:
                        seen_tools.add(name)
                        yield _sse({"type": "tool", "name": name})

                text = chunk.content if isinstance(chunk.content, str) else ""
                if text:
                    yield _sse({"type": "token", "text": text})

            _save_history(user, req.session_id, final_messages)
            yield _sse({
                "type": "done",
                "reply": _last_ai_text(final_messages) or "(no response)",
                "session_id": req.session_id,
            })
        except Exception as exc:
            logger.exception("Streaming failed for session %s", req.session_id)
            yield _sse({
                "type": "error",
                "detail": f"The support agent is temporarily unavailable "
                          f"({type(exc).__name__}).",
            })
        finally:
            context.reset(token)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/me")
def me(user: User = Depends(current_user)):
    """Who am I, and what can I act on — the one call onboarding needs.

    The first call provisions the user's demo orders; later calls just return
    them (`seed_demo_orders` is idempotent). The chat uses these ids for its
    suggestions, so a new user is prompted with orders that are actually theirs
    rather than hardcoded ones they don't own.
    """
    orders = store.seed_demo_orders(user.id)
    return {
        "user": {"id": user.id, "email": user.email, "role": user.role},
        "orders": [
            {"order_id": o["order_id"], "status": o["status"],
             "items": o["items"], "total": o["total"],
             "refundable": o["refundable"]}
            for o in orders
        ],
    }


@app.get("/tickets")
def tickets(user: User = Depends(require_agent)):
    return {"tickets": store.list_tickets()}
