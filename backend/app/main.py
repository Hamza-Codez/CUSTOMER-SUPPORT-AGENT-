"""FastAPI entrypoint.

Handlers are deliberately thin: validate, delegate to the Runner, shape the
response. No policy logic and no data access lives here — policy belongs to
guardrails and tools, data belongs to `app/tools/`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from agents import RunContextWrapper, Runner, RunState
from agents.exceptions import (
    InputGuardrailTripwireTriggered,
    MaxTurnsExceeded,
    OutputGuardrailTripwireTriggered,
)
from agents.items import HandoffOutputItem, ToolCallOutputItem
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.agents.orchestrator import get_entry_agent
from app.core import audit
from app.core.auth import TenantContext, TenantDep
from app.core.config import get_settings
from app.db import get_store, set_store
from app.db.session_store import StoreSession
from app.guardrails.input_guards import REDIRECT_MESSAGE
from app.handoffs.human_escalation import (
    build_decision_card,
    new_escalation,
    restore_evidence,
    to_public_card,
)
from app.schemas import (
    AgentAction,
    ChatRequest,
    ChatResponse,
    DecisionRequest,
    DecisionResponse,
    EscalationList,
    HealthResponse,
)

log = logging.getLogger("fte")

UNGROUNDED_REPLY = (
    "I don't want to guess at that, so let me get a colleague to confirm it for "
    "you. Is there anything else I can help with in the meantime?"
)


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
    version="0.3.0",
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


async def require_operator(tenant: TenantDep) -> TenantContext:
    """Operator-only routes. A customer token must never reach the queue."""
    if tenant.role != "operator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires an operator token.",
        )
    return tenant



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


# --- action chips -------------------------------------------------------------


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
    status_text = str(order.get("status", "")).replace("_", " ")
    return AgentAction(
        kind="order_looked_up", label=f"{ref} · {status_text}".strip(" ·"), ref=ref
    )


def _product_action(payload: dict[str, Any]) -> AgentAction:
    products = payload.get("products") or []
    if not products:
        return AgentAction(kind="no_product_match", label="No catalogue match")
    if len(products) == 1:
        p = products[0]
        return AgentAction(kind="product_viewed", label=p["name"], ref=p["product_id"])
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


def _refund_action(payload: dict[str, Any]) -> AgentAction:
    outcome = payload["outcome"]
    if outcome == "executed":
        return AgentAction(
            kind="refund_executed",
            label=f"Refunded {payload.get('amount')}",
            ref=payload.get("refund_id"),
        )
    if outcome == "already_refunded":
        return AgentAction(kind="refund_duplicate", label="Already refunded")
    return AgentAction(kind="refund_refused", label="Refund refused")


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
        elif "refund_id" in payload:
            actions.append(_refund_action(payload))
        elif "escalation_id" in payload:
            actions.append(
                AgentAction(
                    kind="escalated",
                    label="Escalated to a colleague",
                    ref=payload["escalation_id"],
                )
            )
        else:
            actions.append(_order_action(payload))

    return actions


# --- chat ---------------------------------------------------------------------


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, tenant: TenantDep) -> ChatResponse:
    tenant.session_id = req.session_id
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
    except InputGuardrailTripwireTriggered as trip:
        info = _guardrail_info(trip)
        await audit.record(
            tenant,
            action="input_guardrail",
            target=req.session_id,
            outcome=str(info.get("verdict", "blocked")),
        )
        return ChatResponse(
            reply=REDIRECT_MESSAGE,
            session_id=req.session_id,
            actions=[AgentAction(kind="blocked", label="Off-topic or unsafe request")],
        )
    except OutputGuardrailTripwireTriggered as trip:
        # The agent produced something it could not support. Say less, not more.
        #
        # Agents that must retrieve before speaking now force a tool call in
        # their own model settings, so reaching here should be rare. It stays as
        # the backstop: an ungrounded claim must never reach a customer.
        info = _guardrail_info(trip)
        log.warning("grounding tripwire: %s", info.get("reason"))
        await audit.record(
            tenant,
            action="grounding_guardrail",
            target=req.session_id,
            outcome="tripped",
            reason=str(info.get("reason")),
        )
        return ChatResponse(
            reply=UNGROUNDED_REPLY,
            session_id=req.session_id,
            actions=[AgentAction(kind="ungrounded_blocked", label="Answer withheld")],
        )
    except MaxTurnsExceeded:
        # The agent got stuck in a loop — most often retrying a tool a guardrail
        # keeps refusing. The customer is owed a human, not a stack trace, and
        # the loop itself is worth having in the audit log.
        log.warning("max turns exceeded in session %s", req.session_id)
        await audit.record(
            tenant,
            action="max_turns_exceeded",
            target=req.session_id,
            outcome="looped",
        )
        return ChatResponse(
            reply=(
                "I'm going round in circles on this one, so let me hand you to a "
                "colleague who can sort it out properly. Sorry about that."
            ),
            session_id=req.session_id,
            actions=[AgentAction(kind="agent_stuck", label="Handed to a colleague")],
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

    actions = collect_actions(result)

    # A gated tool paused the run. Nothing has been executed.
    if result.interruptions:
        card, customer_reply = await build_decision_card(
            tenant, list(result.interruptions), req.message
        )
        record = new_escalation(tenant, card, _serialise_state(result))
        await tenant.store.create_escalation(record)
        await audit.record(
            tenant,
            action="approval_required",
            target=record.escalation_id,
            outcome=str(card.get("policy_check", {}).get("reason_code")),
        )
        actions.append(
            AgentAction(
                kind="approval_pending",
                label="Waiting for a colleague to approve",
                ref=record.escalation_id,
            )
        )
        return ChatResponse(
            reply=customer_reply, session_id=req.session_id, actions=actions
        )

    return ChatResponse(
        reply=result.final_output or "",
        session_id=req.session_id,
        actions=actions,
    )


def _guardrail_info(trip: Exception) -> dict[str, Any]:
    result = getattr(trip, "guardrail_result", None)
    info = getattr(getattr(result, "output", None), "output_info", None)
    return info if isinstance(info, dict) else {}


def _plain_context(ctx: Any) -> dict[str, Any]:
    """Serialise only the flat, safe parts of the tenant context.

    Without this the SDK tries to serialise the whole dataclass, which holds a
    live asyncpg pool. Deep-copying that raises, `to_json` fails, and the
    escalation is stored with no run state — so approving records a decision but
    can never execute it. It works on the in-memory store and fails on Postgres,
    which is exactly the kind of difference that only shows up in production.

    Nothing here is trusted on the way back in: resume supplies a live context via
    `context_override` and restores evidence from the Decision Card.
    """
    return {
        "business_id": getattr(ctx, "business_id", None),
        "role": getattr(ctx, "role", None),
        "actor": getattr(ctx, "actor", None),
        "session_id": getattr(ctx, "session_id", None),
    }


def _serialise_state(result: Any) -> dict[str, Any] | None:
    """Serialise a paused run so an operator can resume it later.

    If this fails we still raise the Decision Card: a human being told about a
    paused refund matters far more than resuming it automatically.
    """
    try:
        return result.to_state().to_json(context_serializer=_plain_context)
    except Exception:
        log.exception("could not serialise run state; escalation raised without it")
        return None


# --- operator queue -----------------------------------------------------------


@app.get("/dashboard/escalations", response_model=EscalationList)
async def list_escalations(
    tenant: TenantContext = Depends(require_operator),
    status_filter: str | None = None,
) -> EscalationList:
    records = await tenant.store.list_escalations(
        tenant.business_id, status=status_filter
    )
    return EscalationList(escalations=[to_public_card(r) for r in records])


@app.post("/escalations/{escalation_id}/decision", response_model=DecisionResponse)
async def decide_escalation(
    escalation_id: str,
    req: DecisionRequest,
    tenant: TenantContext = Depends(require_operator),
) -> DecisionResponse:
    """Approve or decline a Decision Card, resuming the paused run either way."""
    record = await tenant.store.get_escalation(tenant.business_id, escalation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No such escalation.")
    if record.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Already {record.status} by {record.resolved_by or 'someone'}.",
        )

    new_status = "approved" if req.decision == "approve" else "declined"

    # Compare-and-set. Two operators clicking Approve at the same moment: one
    # wins, and only one refund can follow.
    claimed = await tenant.store.resolve_escalation(
        tenant.business_id,
        escalation_id,
        status=new_status,
        resolved_by=tenant.actor,
        reason=req.reason,
    )
    if not claimed:
        raise HTTPException(
            status_code=409, detail="This escalation was just resolved by someone else."
        )

    await audit.record(
        tenant,
        action="escalation_decision",
        target=escalation_id,
        outcome=new_status,
        reason=req.reason,
    )

    customer_reply = await _resume(tenant, record, req, new_status)
    return DecisionResponse(
        escalation_id=escalation_id,
        status=new_status,  # type: ignore[arg-type]
        outcome="resumed" if customer_reply is not None else "recorded",
        customer_reply=customer_reply,
    )


async def _resume(
    tenant: TenantContext,
    record: Any,
    req: DecisionRequest,
    new_status: str,
) -> str | None:
    """Continue the paused run with the operator's decision applied.

    The customer's conversation carries on from where it stopped, so the outcome
    arrives in the same thread rather than as a disconnected notification.
    """
    if not record.run_state:
        return None

    tenant.session_id = record.session_id
    # Hand the original run's tool evidence back, or our own guardrails will block
    # the very action the operator just approved. See handoffs/human_escalation.py.
    restore_evidence(tenant, record)
    agent = get_entry_agent()

    try:
        state = await RunState.from_json(
            agent,
            record.run_state,
            # The serialised context carries a dead database pool; this replaces
            # it with the live one from the operator's request.
            context_override=RunContextWrapper(tenant),
        )
        for item in state.get_interruptions():
            if new_status == "approved":
                state.approve(item)
            else:
                state.reject(
                    item,
                    rejection_message=req.reason
                    or "A colleague reviewed this and could not approve it.",
                )

        # Resume on the state alone. Passing `context=` or `session=` here makes
        # the Runner replay the original message and pause all over again, so the
        # refund never executes — the state already carries both.
        result = await Runner.run(agent, state)
    except Exception:
        # The decision is already recorded and is the thing that matters. A failed
        # resume must not make it look like nothing was decided.
        log.exception("could not resume run for %s", record.escalation_id)
        return None

    reply = result.final_output or None
    if reply:
        # Resuming without a session means the outcome is not written to the
        # transcript automatically, so append it: the customer should see the
        # resolution in the same conversation they started.
        try:
            session = StoreSession(
                record.session_id, tenant.business_id, tenant.store
            )
            await session.add_items([{"role": "assistant", "content": reply}])
        except Exception:
            log.exception("could not append resumed reply to session")
    return reply
