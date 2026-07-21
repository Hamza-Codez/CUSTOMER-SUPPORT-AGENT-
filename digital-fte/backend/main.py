"""FastAPI server for the Digital FTE Customer Support Agent.

Endpoints:
    POST /chat     -> send a message, get the agent's reply (with per-session memory)
    GET  /tickets  -> list tickets the agent has created (for the dashboard)
    GET  /health   -> liveness check
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage
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

# Simple in-memory conversation memory: session_id -> list[BaseMessage].
# Swap for Supabase/Redis to persist across restarts.
SESSIONS: dict[str, list] = {}


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
    history = SESSIONS.setdefault(req.session_id, [])
    history.append(HumanMessage(content=req.message))

    try:
        agent = get_agent()
        result = agent.invoke({"messages": history})
    except Exception as exc:  # never leak a stack trace to the customer
        # Drop the un-answered message so a retry starts from clean memory.
        history.pop()
        logger.exception("Agent invocation failed for session %s", req.session_id)
        raise HTTPException(
            status_code=500,
            detail=f"The support agent is temporarily unavailable ({type(exc).__name__}).",
        ) from exc

    # The agent returns the full message list; keep it as the new memory.
    new_messages = result["messages"]
    SESSIONS[req.session_id] = new_messages

    # The reply is the last AI message with text content.
    reply = ""
    for m in reversed(new_messages):
        if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content.strip():
            reply = m.content
            break

    return ChatResponse(
        reply=reply or "(no response)",
        session_id=req.session_id,
        provider=os.getenv("MODEL_PROVIDER", "mock"),
    )


@app.get("/tickets")
def tickets():
    return {"tickets": store.list_tickets()}
