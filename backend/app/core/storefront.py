"""What the storefront knows about the customer standing in front of it.

The widget sits on a page where the customer is already signed in. That page has
their orders, their tracking numbers and their cart on it. Asking "what is your
order number and the email on it" in that setting is not caution, it is the
agent admitting it is a demo — which was the report that produced this file.

**Why this is not "read the DOM".** A page is client-controlled. Anything the
browser hands us, the browser can forge, so a widget that trusted the DOM would
let anyone claim any order simply by editing a variable — the precise attack the
rest of this codebase is built to prevent. So there are two grades of context and
they are never confused:

| Grade | Where it comes from | What it may do |
|---|---|---|
| **attested** | signed by the seller's server with the site key's secret | proves identity; may ground a refund |
| **declared** | handed over by the page, unsigned | may be quoted back; may **not** read our store or move money |

Attested context is *stronger* than the email challenge it replaces: an email
address is something a customer types, whereas this is a cryptographic assertion
by the seller's own server that this person is logged in as this customer.

Declared context still earns its place. A storefront with no backend — a test
project, a static shop — can light up the whole experience with it, and nothing
it says can hurt anyone, because everything it touches is quoted back to the same
browser that supplied it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import jwt

# Signed with the site key's secret, so the seller's server is the only party
# that can mint one. Same algorithm as our session tokens — one primitive.
ALGORITHM = "HS256"

# An assertion is about a customer who is on the page *now*. A long life would
# turn a copied header into a durable credential.
MAX_AGE_SECONDS = 60 * 60

# Bounds on what a page may hand over. Not security — a signed payload is
# trusted — but a storefront looping its entire order table into every request
# would quietly become the slowest part of a conversation.
MAX_ORDERS = 25
MAX_CART_ITEMS = 25


@dataclass
class StorefrontOrder:
    """One order as the storefront describes it.

    Deliberately loose about types: this mirrors whatever the seller's own system
    calls things, and rejecting an order because its status is "out for delivery"
    rather than one of our enum values would make integration a schema argument.
    """

    order_id: str
    status: str = ""
    placed_at: str = ""
    total: str = ""
    item_count: int = 0
    carrier: str = ""
    tracking_number: str = ""
    eta: str = ""
    summary: str = ""

    @classmethod
    def parse(cls, raw: Any) -> "StorefrontOrder | None":
        if not isinstance(raw, dict):
            return None
        order_id = str(raw.get("order_id") or raw.get("id") or "").strip()
        if not order_id:
            return None
        return cls(
            order_id=order_id[:64],
            status=str(raw.get("status") or "")[:48],
            placed_at=str(raw.get("placed_at") or raw.get("date") or "")[:32],
            total=str(raw.get("total") or "")[:24],
            item_count=int(raw.get("item_count") or raw.get("items") or 0),
            carrier=str(raw.get("carrier") or "")[:48],
            tracking_number=str(raw.get("tracking_number") or raw.get("tracking") or "")[:64],
            eta=str(raw.get("eta") or "")[:32],
            summary=str(raw.get("summary") or "")[:160],
        )


@dataclass
class StorefrontCartItem:
    name: str
    quantity: int = 1
    price: str = ""

    @classmethod
    def parse(cls, raw: Any) -> "StorefrontCartItem | None":
        if not isinstance(raw, dict):
            return None
        name = str(raw.get("name") or raw.get("title") or "").strip()
        if not name:
            return None
        return cls(
            name=name[:120],
            quantity=int(raw.get("quantity") or raw.get("qty") or 1),
            price=str(raw.get("price") or "")[:24],
        )


@dataclass
class StorefrontContext:
    """Who the storefront says is here, and what it says they have.

    `verified` is the only field that decides anything. Everything else is a
    description; this is the claim about whether the description can be trusted.
    """

    verified: bool = False
    customer_ref: str = ""
    customer_name: str = ""
    customer_email: str = ""
    orders: list[StorefrontOrder] = field(default_factory=list)
    cart: list[StorefrontCartItem] = field(default_factory=list)
    page_url: str = ""
    page_title: str = ""

    @property
    def grade(self) -> str:
        """For the audit log. A reader should never have to infer this."""
        return "attested" if self.verified else "declared"

    def order(self, order_id: str) -> StorefrontOrder | None:
        wanted = order_id.strip().casefold()
        for order in self.orders:
            if order.order_id.casefold() == wanted:
                return order
        return None

    def order_ids(self) -> list[str]:
        return [o.order_id for o in self.orders]


def _payload_to_context(payload: dict[str, Any], *, verified: bool) -> StorefrontContext:
    customer = payload.get("customer")
    customer = customer if isinstance(customer, dict) else {}
    page = payload.get("page")
    page = page if isinstance(page, dict) else {}

    orders = [
        parsed
        for parsed in (
            StorefrontOrder.parse(o) for o in (payload.get("orders") or [])[:MAX_ORDERS]
        )
        if parsed is not None
    ]
    cart = [
        parsed
        for parsed in (
            StorefrontCartItem.parse(c)
            for c in (payload.get("cart") or [])[:MAX_CART_ITEMS]
        )
        if parsed is not None
    ]

    return StorefrontContext(
        verified=verified,
        customer_ref=str(customer.get("ref") or customer.get("id") or "")[:120],
        customer_name=str(customer.get("name") or "")[:120],
        # Only ever read from an attested payload. An unsigned page claiming an
        # email address is a customer typing an email address with extra steps,
        # and that address is what the summary mailer would send to.
        customer_email=(str(customer.get("email") or "")[:254] if verified else ""),
        orders=orders,
        cart=cart,
        page_url=str(page.get("url") or "")[:300],
        page_title=str(page.get("title") or "")[:200],
    )


def sign_context(secret: str, payload: dict[str, Any], *, expires_in: int = 900) -> str:
    """Mint an assertion. Lives here so the docs and the tests sign it the same way.

    The seller's server calls the equivalent of this in their own language; this
    implementation is the reference, and what `tests/test_storefront.py` checks
    the verifier against.
    """
    now = int(datetime.now(timezone.utc).timestamp())
    claims = dict(payload)
    claims.update({"iat": now, "exp": now + expires_in})
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def read_context(
    token: str | None, secret: str | None
) -> tuple[StorefrontContext | None, str]:
    """Verify an assertion. Returns (context, reason-if-rejected).

    A bad signature returns *nothing*, never a downgrade to declared. Silently
    accepting a forged token as merely-untrusted would mean an attacker's payload
    and an honest page's payload were handled identically, which is the kind of
    fallback that turns a signature check into decoration.
    """
    if not token:
        return None, "no token"
    if not secret:
        return None, "key has no secret"

    try:
        claims = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None, "expired"
    except jwt.InvalidTokenError:
        return None, "invalid signature"

    issued = claims.get("iat")
    if isinstance(issued, (int, float)):
        age = datetime.now(timezone.utc).timestamp() - issued
        if age > MAX_AGE_SECONDS:
            return None, "too old"

    return _payload_to_context(claims, verified=True), ""


def read_declared(payload: Any) -> StorefrontContext | None:
    """Take an unsigned payload at face value, and mark it as such."""
    if not isinstance(payload, dict):
        return None
    return _payload_to_context(payload, verified=False)
