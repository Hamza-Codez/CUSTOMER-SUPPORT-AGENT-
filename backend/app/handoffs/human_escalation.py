"""Decision Cards — turning a paused run into something a human can act on.

When `refund_processor` is gated, the SDK stops the run and hands back an
approval item. That is machine state; an operator needs a sentence. This module
turns one into the other, and keeps the serialised run alongside it so approving
resumes the original run rather than starting a new one.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.core.auth import TenantContext
from app.db.base import EscalationRecord, OrderRecord
from app.schemas import DecisionCard

# Why a human was asked, in words an operator can act on.
REASON_TEXT = {
    "over_auto_cap": "Above the automatic refund limit",
    "outside_refund_window": "Outside the refund window",
    "not_delivered": "Order has not been delivered yet",
    "order_not_found": "Order could not be found",
}


def _call_arguments(item: Any) -> dict[str, Any]:
    raw = getattr(getattr(item, "raw_item", None), "arguments", None)
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}


async def build_decision_card(
    tenant: TenantContext,
    interruptions: list[Any],
    customer_message: str,
) -> tuple[dict[str, Any], str]:
    """Build the card payload and a customer-facing sentence.

    Every field comes from a tool result or the run's recorded evidence — never
    from the model asserting something. That is what makes one-click approval safe.
    """
    item = interruptions[0]
    args = _call_arguments(item)
    order_id = str(args.get("order_id", "")).upper()
    amount = args.get("amount")

    record: OrderRecord | None = None
    if order_id:
        record = await tenant.store.get_order(tenant.business_id, order_id)

    reason_codes = list(tenant.pending_approval_reason) or ["review_required"]
    card = {
        "customer": {
            "name": record.customer_name if record else None,
            "verified": order_id in tenant.verified_orders,
            "via": "order+email" if order_id in tenant.verified_orders else None,
        },
        "request": (
            f"Refund {amount} for order {order_id} — {args.get('reason') or 'no reason given'}"
            if order_id
            else customer_message[:200]
        ),
        "policy_check": {
            "reason_codes": reason_codes,
            "result": " · ".join(
                REASON_TEXT.get(code, "Needs a human decision") for code in reason_codes
            ),
            "sources": list(tenant.sources),
            "order_status": record.status if record else None,
            "delivered_on": record.eta if record else None,
        },
        "proposed_action": {
            "type": "refund",
            "order_id": order_id,
            "amount": f"{float(amount):.2f}" if amount is not None else None,
            "method": "original payment method",
        },
        "options": ["approve", "decline"],
        "tool_name": getattr(item, "tool_name", None),
        # The run's evidence, carried so the resumed run can be given it back.
        #
        # Resuming replaces the serialised context (it holds a dead database pool)
        # with a live one, which starts empty — and an empty context means the
        # refund guardrail sees no verified identity and the grounding guardrail
        # sees no tool calls, so approving would be blocked by our own safety
        # layers. Restoring what the tools actually recorded is what makes the
        # operator's approval executable. It is replay of fact, not of trust:
        # every entry was written by a tool that ran.
        "evidence": {
            "tools_used": list(tenant.tools_used),
            "sources": list(tenant.sources),
            "verified_orders": sorted(tenant.verified_orders),
        },
    }

    customer_reply = (
        "Thanks for your patience — I've passed this to a colleague to review, "
        "because it needs a person to sign it off. They'll be in touch shortly, "
        "and I haven't taken any money-related action in the meantime."
    )
    return card, customer_reply


def new_escalation(
    tenant: TenantContext,
    card: dict[str, Any],
    run_state: dict[str, Any] | None,
) -> EscalationRecord:
    return EscalationRecord(
        escalation_id=f"esc_{uuid.uuid4().hex[:10]}",
        business_id=tenant.business_id,
        session_id=tenant.session_id,
        status="pending",
        decision_card=card,
        run_state=run_state,
    )


def restore_evidence(tenant: TenantContext, record: EscalationRecord) -> None:
    """Put the original run's tool evidence back onto a fresh context."""
    evidence = (record.decision_card or {}).get("evidence") or {}
    tenant.tools_used = list(evidence.get("tools_used") or [])
    tenant.sources = list(evidence.get("sources") or [])
    tenant.verified_orders = set(evidence.get("verified_orders") or [])


def to_public_card(record: EscalationRecord) -> DecisionCard:
    card = record.decision_card or {}
    return DecisionCard(
        escalation_id=record.escalation_id,
        status=record.status,  # type: ignore[arg-type]
        created_at=record.created_at.isoformat(),
        customer=card.get("customer", {}),
        request=card.get("request", ""),
        policy_check=card.get("policy_check", {}),
        proposed_action=card.get("proposed_action", {}),
        options=card.get("options", ["approve", "decline"]),
        resolved_by=record.resolved_by,
        resolution_reason=record.resolution_reason,
    )
