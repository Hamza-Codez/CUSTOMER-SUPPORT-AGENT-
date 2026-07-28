"""Refund eligibility — the money-moving safety layer.

Everything here runs before `refund_processor` can execute, and none of it can be
argued with. The model chooses *whether to attempt* a refund; this module decides
whether one is allowed and whether a human must sign it off.

Split by consequence:

- **Tool input guardrail** — refuses outright. Used where the request is simply
  not permissible: an unverified identity, an unknown order, an amount that does
  not match the order. The model is told why and can correct course.
- **`needs_approval`** — pauses instead of refusing. Used where the refund may
  well be right but is not ours to make: over the auto-cap, outside the refund
  window, or an order that never arrived. A human gets a Decision Card.

The distinction matters. Refusing a legitimate over-cap refund would be wrong;
executing it silently would be worse. Pausing is the honest third option.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from agents import (
    RunContextWrapper,
    ToolGuardrailFunctionOutput,
    ToolInputGuardrailData,
    tool_input_guardrail,
)

from app.core.auth import TenantContext
from app.core.config import get_settings
from app.db.base import OrderRecord
from app.tools.orders import normalise_order_id


def days_since_delivery(record: OrderRecord, today: date | None = None) -> int | None:
    """Days since the order was delivered, or None if it has not been.

    `today` is injectable so the window logic can be tested at fixed dates rather
    than drifting with the calendar.
    """
    if record.status != "delivered" or not record.eta:
        return None
    try:
        delivered = date.fromisoformat(record.eta)
    except ValueError:
        return None
    return ((today or date.today()) - delivered).days


def _args(data: ToolInputGuardrailData) -> dict[str, Any]:
    raw = getattr(data.context, "tool_arguments", None)
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}


@tool_input_guardrail
async def refund_precheck(data: ToolInputGuardrailData) -> ToolGuardrailFunctionOutput:
    """Refuse refunds that must never happen, whatever the conversation said."""
    tenant: TenantContext = data.context.context
    args = _args(data)
    order_id = normalise_order_id(str(args.get("order_id", "")))

    # 1. Identity. `verified_orders` is written by order_lookup when an email
    #    actually matched. The model cannot talk its way onto that list.
    if order_id not in tenant.verified_orders:
        return ToolGuardrailFunctionOutput.reject_content(
            message=(
                f"Refund blocked: identity for {order_id or 'that order'} has not been "
                "verified in this conversation. Call order_lookup with the order id and "
                "the email on the order first, and only continue if it returns 'found'."
            ),
            output_info={"reason": "identity_not_verified", "order_id": order_id},
        )

    record = await tenant.store.get_order(tenant.business_id, order_id)
    if record is None:
        # The storefront vouched for this order but we have never held it — the
        # seller keeps their own order data. We can discuss it and we can check
        # the policy against it, but we hold no payment record to refund against,
        # so this is a person's decision rather than a missing order.
        front = tenant.storefront
        if front is not None and front.verified and front.order(order_id) is not None:
            return ToolGuardrailFunctionOutput.reject_content(
                message=(
                    f"Refund blocked: order {order_id} is held in the store's own "
                    "system, not ours, so there is nothing here to refund against. "
                    "Use human_escalation so a colleague can action it, and tell "
                    "the customer it is with a person."
                ),
                output_info={"reason": "order_not_ours", "order_id": order_id},
            )
        return ToolGuardrailFunctionOutput.reject_content(
            message=f"Refund blocked: no order {order_id} exists on this account.",
            output_info={"reason": "order_not_found", "order_id": order_id},
        )

    # 2. The amount must be the order's amount. Refunding more than was paid is
    #    not a judgement call a human should be asked to rubber-stamp either.
    try:
        requested = float(args.get("amount") or 0)
    except (TypeError, ValueError):
        requested = -1.0

    if requested <= 0:
        return ToolGuardrailFunctionOutput.reject_content(
            message="Refund blocked: the amount must be a positive number.",
            output_info={"reason": "invalid_amount", "amount": args.get("amount")},
        )

    if abs(requested - float(record.total)) > 0.005:
        return ToolGuardrailFunctionOutput.reject_content(
            message=(
                f"Refund blocked: {requested:.2f} does not match the order total "
                f"({record.total}). Partial and inflated refunds are not supported; "
                f"refund the full order total or escalate to a colleague."
            ),
            output_info={"reason": "amount_mismatch", "order_total": record.total},
        )

    # 3. Already refunded. Caught here as well as by the unique constraint, so the
    #    model gets a sentence it can explain rather than a database error.
    existing = await tenant.store.get_refund(tenant.business_id, order_id)
    if existing is not None:
        return ToolGuardrailFunctionOutput.reject_content(
            message=(
                f"Refund blocked: order {order_id} was already refunded "
                f"({existing.refund_id}). Tell the customer it is already on its way."
            ),
            output_info={"reason": "already_refunded", "refund_id": existing.refund_id},
        )

    return ToolGuardrailFunctionOutput.allow(
        output_info={"order_id": order_id, "amount": requested}
    )


def approval_reasons(
    record: OrderRecord | None,
    amount: float,
    *,
    cap: float,
    window_days: int,
    today: date | None = None,
) -> list[str]:
    """Every reason a human must decide this refund. Empty means the agent may proceed.

    All applicable reasons are returned, not the first one found. An order that is
    both over the cap and outside the window is a different decision from one that
    is merely expensive, and the operator should see both rather than having to
    infer the second from the dates.

    Pure function: the actual policy, in one testable place.
    """
    if record is None:
        return ["order_not_found"]

    reasons: list[str] = []
    if amount > cap:
        reasons.append("over_auto_cap")

    elapsed = days_since_delivery(record, today)
    if elapsed is None:
        reasons.append("not_delivered")
    elif elapsed > window_days:
        reasons.append("outside_refund_window")

    return reasons


async def refund_needs_approval(
    ctx: RunContextWrapper[TenantContext],
    params: dict[str, Any],
    call_id: str,
) -> bool:
    """Called by the SDK before executing `refund_processor`.

    Returning True pauses the run: no refund happens, a Decision Card is raised,
    and execution only continues once an operator approves.
    """
    settings = get_settings()
    tenant = ctx.context
    order_id = normalise_order_id(str(params.get("order_id", "")))

    try:
        amount = float(params.get("amount") or 0)
    except (TypeError, ValueError):
        return True  # unparseable amounts are never auto-approved

    record = await tenant.store.get_order(tenant.business_id, order_id)
    reasons = approval_reasons(
        record,
        amount,
        cap=settings.auto_refund_cap,
        window_days=settings.refund_window_days,
    )

    if reasons:
        # Stashed so the Decision Card can state *why* a human was needed.
        tenant.pending_approval_reason = reasons
    return bool(reasons)
