"""FastAPI server for the Digital FTE Customer Support Agent.

Endpoints:
    POST /chat     -> send a message, get the agent's reply (with per-session memory)
    GET  /tickets  -> list tickets the agent has created (for the dashboard)
    GET  /health   -> liveness check
"""
from __future__ import annotations

import json
import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import (AIMessage, AIMessageChunk, HumanMessage,
                                     messages_from_dict, messages_to_dict)
from pydantic import BaseModel

import store
from agent import get_agent

logger = logging.getLogger("digital-fte")

app = FastAPI(title="Digital FTE — Customer Support Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)

def _load_history(session_id: str) -> list:
    """Session memory lives in the data layer; this converts it to LangChain
    messages. The store holds plain JSON dicts and never imports LangChain."""
    return messages_from_dict(store.get_session(session_id))


def _save_history(session_id: str, messages: list) -> None:
    store.save_session(session_id, messages_to_dict(messages))


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
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    history = _load_history(req.session_id)
    history.append(HumanMessage(content=req.message))

    try:
        result = get_agent().invoke({"messages": history})
    except Exception as exc:  # never leak a stack trace to the customer
        # History is not saved, so a retry starts from clean memory.
        logger.exception("Agent invocation failed for session %s", req.session_id)
        raise HTTPException(
            status_code=500,
            detail=f"The support agent is temporarily unavailable ({type(exc).__name__}).",
        ) from exc

    # The agent returns the full message list; keep it as the new memory.
    _save_history(req.session_id, result["messages"])

    return ChatResponse(
        reply=_last_ai_text(result["messages"]) or "(no response)",
        session_id=req.session_id,
        provider=os.getenv("MODEL_PROVIDER", "mock"),
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Same conversation as /chat, delivered as Server-Sent Events.

    Frames: {"type": "tool", "name": ...} when a tool starts,
            {"type": "token", "text": ...} for each text delta,
            {"type": "done", "reply": ..., "session_id": ...} once,
            {"type": "error", "detail": ...} if the agent fails.

    Errors arrive as a frame, not an HTTP status: by the time the agent fails
    the response has already started streaming and the status line is long gone.
    """
    history = _load_history(req.session_id)
    history.append(HumanMessage(content=req.message))

    async def events():
        final_messages = list(history)
        seen_tools: set[str] = set()
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

            _save_history(req.session_id, final_messages)
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

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/tickets")
def tickets():
    return {"tickets": store.list_tickets()}
