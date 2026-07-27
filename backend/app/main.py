"""FastAPI entrypoint.

Handlers are deliberately thin: validate, delegate to the Runner, shape the
response. No policy logic and no data access lives here — policy belongs to
guardrails and tools, data belongs to `app/tools/`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from agents import Runner
from agents.items import HandoffOutputItem, ToolCallOutputItem
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.agents.orchestrator import get_entry_agent
from app.core.auth import TenantDep
from app.core.config import get_settings
from app.db import get_store, set_store
from app.db.session_store import StoreSession
from app.schemas import AgentAction, ChatRequest, ChatResponse, HealthResponse

log = logging.getLogger("fte")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = get_store()
    await store.connect()
    try:
        yield
    finally:
        await store.close()
        set_store(None)


app = FastAPI(
    title="Digital FTE — Agent Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Open in dev. Tighten `allow_origins` before this is exposed anywhere real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness plus which provider and store are actually live.

    Reports a degraded database rather than raising, so this endpoint stays
    usable for exactly the situation it exists to diagnose.
    """
    settings = get_settings()
    db_up = await get_store().health()
    return HealthResponse(
        status="ok" if db_up else "degraded",
        provider=settings.model_provider,
        store=settings.store_kind,
        db="up" if db_up else "down",
    )


def _tool_payload(item: ToolCallOutputItem) -> dict[str, Any] | None:
    """Normalise a tool result to a dict, whatever concrete form it arrived in."""
    output = item.output
    if isinstance(output, dict):
        return output
    dump = getattr(output, "model_dump", None)
    return dump() if callable(dump) else None


def _order_action(payload: dict[str, Any]) -> AgentAction:
    outcome = payload["outcome"]
    if outcome == "identity_mismatch":
        return AgentAction(kind="identity_check_failed", label="Identity not verified")
    if outcome == "not_found":
        return AgentAction(kind="order_not_found", label="Order not found")

    order = payload.get("order") or {}
    ref = order.get("order_id")
    status = str(order.get("status", "")).replace("_", " ")
    return AgentAction(
        kind="order_looked_up", label=f"{ref} · {status}".strip(" ·"), ref=ref
    )


def _product_action(payload: dict[str, Any]) -> AgentAction:
    products = payload.get("products") or []
    if not products:
        return AgentAction(kind="no_product_match", label="No catalogue match")
    if len(products) == 1:
        p = products[0]
        return AgentAction(
            kind="product_viewed", label=p["name"], ref=p["product_id"]
        )
    return AgentAction(
        kind="products_compared",
        label=" vs ".join(p["name"] for p in products),
        ref=",".join(p["product_id"] for p in products),
    )


def _policy_action(payload: dict[str, Any]) -> AgentAction:
    passages = payload.get("passages") or []
    if not passages:
        return AgentAction(kind="no_policy_match", label="No grounded policy found")
    return AgentAction(
        kind="policy_cited",
        label=passages[0]["topic"],
        ref=passages[0]["source_ref"],
    )


def collect_actions(result: Any) -> list[AgentAction]:
    """Derive UI action chips from what the agent actually did.

    Every chip is built from a real handoff or a real tool result, so a chip can
    only appear if the thing it describes actually happened.
    """
    actions: list[AgentAction] = []

    for item in result.new_items:
        if isinstance(item, HandoffOutputItem):
            actions.append(
                AgentAction(
                    kind="routed",
                    label=f"Routed to {item.target_agent.name}",
                    ref=item.target_agent.name,
                )
            )
            continue

        if not isinstance(item, ToolCallOutputItem):
            continue
        payload = _tool_payload(item)
        if not payload or "outcome" not in payload:
            continue

        # Which tool produced this is read off the payload's shape rather than
        # tracked separately — the result schemas are disjoint by construction.
        if "products" in payload:
            actions.append(_product_action(payload))
        elif "passages" in payload:
            actions.append(_policy_action(payload))
        else:
            actions.append(_order_action(payload))

    return actions


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, tenant: TenantDep) -> ChatResponse:
    session = StoreSession(
        session_id=req.session_id,
        business_id=tenant.business_id,
        store=tenant.store,
    )

    try:
        result = await Runner.run(
            get_entry_agent(),
            input=req.message,
            context=tenant,
            session=session,
        )
    except Exception as exc:
        # The agent run failing is an infrastructure problem (bad key, provider
        # unreachable), not a conversation outcome. Surface it as a clear error
        # rather than a reply that looks like the agent answered.
        log.exception("agent run failed")
        raise HTTPException(
            status_code=502,
            detail=f"Agent run failed: {type(exc).__name__}: {exc}",
        ) from exc

    return ChatResponse(
        reply=result.final_output or "",
        session_id=req.session_id,
        actions=collect_actions(result),
    )
