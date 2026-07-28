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
from app.schemas import (
    CartLine,
    MyOrder,
    MyOrdersResult,
    OrderLookupResult,
    OrderStatus,
)

_ORDER_ID_RE = re.compile(r"^ORD-?(\d+)$", re.IGNORECASE)


def normalise_order_id(raw: str) -> str:
    """Accept 'ord 1002', 'ORD1002', ' ord-1002 ' — customers type all of these."""
    candidate = re.sub(r"\s+", "", raw or "").upper()
    match = _ORDER_ID_RE.match(candidate)
    return f"ORD-{match.group(1)}" if match else candidate


@function_tool
async def my_orders(ctx: RunContextWrapper[TenantContext]) -> MyOrdersResult:
    """What this customer has with the store: their orders and their basket.

    Use this FIRST whenever someone asks about "my order", "my delivery", "where
    is it", what is in their cart or basket, or wants a refund. It takes no
    parameters — you cannot choose whose orders to list, and there is nothing to
    ask the customer for.

    If it returns orders, name them and their status directly. Do not ask for an
    order number or an email address: you already have the orders.

    Keep orders and basket apart when you answer. An order is paid for and on its
    way; a basket line is not bought yet, and telling someone their basket has
    shipped is worse than saying nothing.

    If it returns `no_session` or `none`, fall back to asking for the order id
    and the email on it, and use `order_lookup`.
    """
    tenant = ctx.context
    tenant.note_tool("my_orders")
    front = tenant.storefront

    # The basket travels with every answer. It is the same question — what
    # have I got with you — and it only ever comes from the page, because a
    # basket is not something we hold.
    basket = (
        [
            CartLine(name=c.name, quantity=c.quantity, price=c.price)
            for c in front.cart
        ]
        if front is not None
        else []
    )

    if front is None or (
        not front.orders and not front.customer_email and not front.cart
    ):
        await audit.record(
            tenant, action="my_orders", target="session", outcome="no_session"
        )
        return MyOrdersResult(
            outcome="no_session",
            message=(
                "Nobody is signed in on this page, so there is no list of orders. "
                "Ask for the order id and the email on it instead."
            ),
        )

    # Preferred path: the storefront proved who this is, so our own records can
    # be read for them. This is the only branch that touches the database, and it
    # is reachable only from a signed assertion.
    if front.verified and front.customer_email:
        owned = [
            record
            for record in await tenant.store.list_orders(tenant.business_id, limit=200)
            if record.customer_email.casefold() == front.customer_email.casefold()
        ]
        if owned:
            for record in owned:
                tenant.note_verified(record.order_id)
            tenant.verified_email = front.customer_email
            tenant.verified_name = front.customer_name or owned[0].customer_name

            await audit.record(
                tenant,
                action="my_orders",
                target=front.customer_ref or front.customer_email,
                outcome="found",
                source="store",
                count=len(owned),
            )
            return MyOrdersResult(
                outcome="found",
                source="store",
                customer_name=tenant.verified_name or "",
                orders=[
                    MyOrder(
                        order_id=r.order_id,
                        status=r.status,
                        placed_at=r.placed_at,
                        total=r.total,
                        item_count=r.item_count,
                        carrier=r.carrier or "",
                        tracking_number=r.tracking_number or "",
                        eta=r.eta or "",
                    )
                    for r in owned
                ],
                cart=basket,
                message=f"{len(owned)} order(s) on this account.",
            )

    # The storefront keeps its own order data and told us about it. Attested
    # orders count as verified for this run; declared ones never do.
    if front.orders:
        if front.verified:
            for order in front.orders:
                tenant.note_verified(order.order_id)
            if front.customer_email:
                tenant.verified_email = front.customer_email
            tenant.verified_name = front.customer_name or tenant.verified_name

        await audit.record(
            tenant,
            action="my_orders",
            target=front.customer_ref or "storefront",
            outcome="found",
            source=front.grade,
            count=len(front.orders),
        )
        return MyOrdersResult(
            outcome="found",
            source="storefront" if front.verified else "declared",
            customer_name=front.customer_name,
            orders=[
                MyOrder(
                    order_id=o.order_id,
                    status=o.status,
                    placed_at=o.placed_at,
                    total=o.total,
                    item_count=o.item_count,
                    carrier=o.carrier,
                    tracking_number=o.tracking_number,
                    eta=o.eta,
                )
                for o in front.orders
            ],
            cart=basket,
            message=(
                f"{len(front.orders)} order(s), from the store page itself."
                if front.verified
                else (
                    f"{len(front.orders)} order(s) as shown on the page. These are "
                    "unverified, so you may discuss them but must not act on them: "
                    "any refund needs a colleague."
                )
            ),
        )

    # No orders, but possibly a basket — someone browsing who has not bought yet
    # is a real customer with a real question, not an empty result.
    if basket:
        await audit.record(
            tenant,
            action="my_orders",
            target=front.customer_ref or "storefront",
            outcome="found",
            source=front.grade,
            count=0,
        )
        return MyOrdersResult(
            outcome="found",
            source="storefront" if front.verified else "declared",
            customer_name=front.customer_name,
            cart=basket,
            message=(
                f"No orders yet, but {len(basket)} item(s) in the basket. "
                "Nothing here is bought — do not describe it as an order."
            ),
        )

    await audit.record(
        tenant, action="my_orders", target="session", outcome="none", source=front.grade
    )
    return MyOrdersResult(
        outcome="none",
        customer_name=front.customer_name,
        message="This customer has no orders and an empty basket.",
    )


@function_tool
async def order_lookup(
    ctx: RunContextWrapper[TenantContext],
    order_id: str,
    email: str,
) -> OrderLookupResult:
    """Look up one order and return its current status.

    Use this when the customer names an order you do not already have from
    `my_orders`. It requires BOTH the order id (like ORD-1002) and the email
    address on the order. If the customer has not given you both, ask for the
    missing one before calling this tool — do not guess or invent either.

    If the storefront has already identified the customer, you do not need to
    ask: pass their order id and leave the email empty, and identity is taken
    from the store page's own assertion instead.
    """
    tenant = ctx.context
    tenant.note_tool("order_lookup")
    normalised = normalise_order_id(order_id)
    supplied_email = (email or "").strip()

    # Identity already proven by the storefront, for this exact order. The email
    # challenge exists to answer "is this your order?"; a signed assertion from
    # the seller's own server answers it better than an address a customer typed.
    front = tenant.storefront
    attested = (
        front is not None
        and front.verified
        and front.order(normalised) is not None
    )
    if attested and not supplied_email:
        supplied_email = front.customer_email

    record = await tenant.store.get_order(tenant.business_id, normalised)

    # The storefront vouched for an order we have never held. Answer from what it
    # told us rather than claiming the order does not exist — for a seller whose
    # orders live in their own system, ours is the incomplete record, not theirs.
    if record is None and attested:
        described = front.order(normalised)
        tenant.note_verified(normalised)
        if front.customer_email:
            tenant.verified_email = front.customer_email
        tenant.verified_name = front.customer_name or tenant.verified_name
        await audit.record(
            tenant,
            action="order_lookup",
            target=normalised,
            outcome="found",
            source="storefront",
            status=described.status,
        )
        return OrderLookupResult(
            outcome="found",
            order=OrderStatus(
                order_id=described.order_id,
                status=described.status or "unknown",
                placed_at=described.placed_at,
                carrier=described.carrier or None,
                tracking_number=described.tracking_number or None,
                eta=described.eta or None,
                item_count=described.item_count,
                total=described.total,
            ),
            message=f"Order {normalised} found.",
        )

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
