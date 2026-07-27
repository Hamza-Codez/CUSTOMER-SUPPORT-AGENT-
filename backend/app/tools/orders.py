"""Order tools — part of the data frontier.

Everything in `app/tools/` is the only code permitted to reach the data layer.
Each tool: resolves tenancy from the run context, verifies identity, reads a
scoped subset, writes an audit record, and returns a typed result.

Note what is *not* a parameter here: `business_id`. It comes from the
authenticated request via `RunContextWrapper`, so a model that hallucinates or
is talked into naming another tenant still cannot reach that tenant's rows.
"""

from __future__ import annotations

import re

from agents import RunContextWrapper, function_tool

from app.core import audit
from app.core.auth import TenantContext
from app.db.base import VerificationRecord
from app.schemas import OrderLookupResult, OrderStatus

_ORDER_ID_RE = re.compile(r"^ORD-?(\d+)$", re.IGNORECASE)


def normalise_order_id(raw: str) -> str:
    """Accept 'ord 1002', 'ORD1002', ' ord-1002 ' — customers type all of these."""
    candidate = re.sub(r"\s+", "", raw or "").upper()
    match = _ORDER_ID_RE.match(candidate)
    return f"ORD-{match.group(1)}" if match else candidate


@function_tool
async def order_lookup(
    ctx: RunContextWrapper[TenantContext],
    order_id: str,
    email: str,
) -> OrderLookupResult:
    """Look up one order and return its current status.

    Use this whenever the customer asks where an order is, when it will arrive,
    or what state it is in. It requires BOTH the order id (like ORD-1002) and the
    email address on the order. If the customer has not given you both, ask for
    the missing one before calling this tool — do not guess or invent either.
    """
    tenant = ctx.context
    tenant.note_tool("order_lookup")
    normalised = normalise_order_id(order_id)
    supplied_email = (email or "").strip()

    record = await tenant.store.get_order(tenant.business_id, normalised)

    if record is None:
        await audit.record(
            tenant,
            action="order_lookup",
            target=normalised,
            outcome="not_found",
        )
        return OrderLookupResult(
            outcome="not_found",
            message=f"No order {normalised} exists on this account.",
        )

    # Identity gate. The order exists, but it is only this customer's order if the
    # email matches — so the refusal is deliberately indistinguishable in content
    # from a match failure, and it is logged.
    if record.customer_email.casefold() != supplied_email.casefold():
        await audit.record(
            tenant,
            action="order_lookup",
            target=normalised,
            outcome="identity_mismatch",
            supplied_email=supplied_email,
        )
        return OrderLookupResult(
            outcome="identity_mismatch",
            message=(
                f"The email supplied does not match the one on order {normalised}. "
                "Details withheld until identity is verified."
            ),
        )

    # Identity proven for this order, in this run. `refund_processor` may only
    # touch orders that appear here — the model cannot assert its way onto the list.
    tenant.note_verified(normalised)
    # The proven address, kept out of the tool's return value but available to the
    # mailer. The customer's own email is the only address we will ever send to.
    tenant.verified_email = record.customer_email
    tenant.verified_name = record.customer_name

    # Remembered for the rest of the conversation. Without this, verification
    # dies with the turn and a customer who has just proved who they are is a
    # stranger again by their next message.
    await tenant.store.add_verification(
        VerificationRecord(
            business_id=tenant.business_id,
            session_id=tenant.session_id,
            order_id=normalised,
            email=record.customer_email,
            name=record.customer_name,
        )
    )

    await audit.record(
        tenant,
        action="order_lookup",
        target=normalised,
        outcome="found",
        status=record.status,
    )

    # Scoped projection: the customer's email and name are dropped here and never
    # reach the model.
    return OrderLookupResult(
        outcome="found",
        order=OrderStatus(
            order_id=record.order_id,
            status=record.status,
            placed_at=record.placed_at,
            carrier=record.carrier,
            tracking_number=record.tracking_number,
            eta=record.eta,
            item_count=record.item_count,
            total=record.total,
        ),
        message=f"Order {normalised} found.",
    )
