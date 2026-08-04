"""Refund and escalation tools — the write side of the frontier.

`refund_processor` is the only tool in the system that moves money, and it has
never existed in an ungated state. It ships with its identity check, its amount
check, its auto-cap and its approval pause attached, because a money-moving tool
that exists before its guardrails is a tool that can move money without them.

By the time the body of the function runs, the request has already survived
`refund_precheck` (which refuses what must not happen) and `refund_needs_approval`
(which pauses what is not ours to decide). The function itself is therefore
deliberately dull: write the record, return the result.
"""

from __future__ import annotations

import uuid

from agents import RunContextWrapper, function_tool

from app.core import audit
from app.core.auth import TenantContext
from app.db.base import EscalationRecord, RefundRecord
from app.guardrails.refund_guard import refund_needs_approval, refund_precheck
from app.schemas import EscalationResult, RefundResult
from app.tools.orders import normalise_order_id


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@function_tool(
    needs_approval=refund_needs_approval,
    tool_input_guardrails=[refund_precheck],
)
async def refund_processor(
    ctx: RunContextWrapper[TenantContext],
    order_id: str,
    amount: float,
    reason: str,
) -> RefundResult:
    """Issue a refund for an order, for the full order total.

    Only call this once you have verified the customer's identity with
    `order_lookup` and checked the refund policy with `policy_retriever`.

    Pass the order's full total as `amount`. You do not decide whether the refund
    is allowed — limits and eligibility are enforced outside this tool. Small,
    recent, in-policy refunds complete immediately; anything larger or older is
    routed to a colleague for approval, and you should tell the customer that a
    colleague is reviewing it. Never tell a customer money has been returned
    unless this tool reports 'executed'.
    """
    tenant = ctx.context
    tenant.note_tool("refund_processor")
    normalised = normalise_order_id(order_id)

    record = RefundRecord(
        refund_id=_new_id("ref"),
        business_id=tenant.business_id,
        order_id=normalised,
        amount=f"{float(amount):.2f}",
        reason=reason or "",
        status="executed",
        approved_by=tenant.actor,
    )

    created = await store_refund(tenant, record)
    if not created:
        existing = await tenant.store.get_refund(tenant.business_id, normalised)
        return RefundResult(
            outcome="already_refunded",
            refund_id=existing.refund_id if existing else None,
            amount=existing.amount if existing else None,
            message=f"Order {normalised} had already been refunded.",
        )

    return RefundResult(
        outcome="executed",
        refund_id=record.refund_id,
        amount=record.amount,
        message=f"Refund of {record.amount} issued for {normalised}.",
    )


async def store_refund(tenant: TenantContext, record: RefundRecord) -> bool:
    created = await tenant.store.create_refund(record)
    if created:
        # For Flavour A this might be a no-op or return an escalation response.
        # For Flavour B this hits the actual Shopify/external API.
        await tenant.adapter.create_refund(
            business_id=tenant.business_id,
            order_id=record.order_id,
            amount=record.amount,
            reason=record.reason
        )

    await audit.record(
        tenant,
        action="refund_processor",
        target=record.order_id,
        outcome="executed" if created else "duplicate_blocked",
        amount=record.amount,
        refund_id=record.refund_id,
    )
    return created


@function_tool
async def human_escalation(
    ctx: RunContextWrapper[TenantContext],
    summary: str,
    reason: str,
) -> EscalationResult:
    """Hand this conversation to a human colleague with full context.

    Use this when the customer is upset or asks for a person, when a request sits
    outside what the written policy covers, or when you are not confident enough
    to answer. Escalating is a good outcome, not a failure — it is how a customer
    gets a decision you are not able to make.

    `summary` is what the customer wants, in one sentence. `reason` is why it
    needs a person.
    """
    tenant = ctx.context
    tenant.note_tool("human_escalation")

    escalation_id = _new_id("esc")
    await tenant.store.create_escalation(
        EscalationRecord(
            escalation_id=escalation_id,
            business_id=tenant.business_id,
            session_id=tenant.session_id,
            status="pending",
            decision_card={
                "customer": {
                    "verified_orders": sorted(tenant.verified_orders),
                    "verified": bool(tenant.verified_orders),
                },
                "request": summary,
                "policy_check": {
                    "sources": list(tenant.sources),
                    "result": "needs_human",
                    "reason": reason,
                },
                "proposed_action": {"type": "review"},
                "options": ["approve", "decline"],
            },
        )
    )

    await audit.record(
        tenant,
        action="human_escalation",
        target=escalation_id,
        outcome="created",
        reason=reason,
    )

    return EscalationResult(
        outcome="escalated",
        escalation_id=escalation_id,
        message=(
            "A colleague has been notified and will follow up. Tell the customer "
            "this is with a person now — do not promise an outcome."
        ),
    )
