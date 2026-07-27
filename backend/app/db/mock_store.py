"""In-memory store: the zero-setup path.

This is what makes `MODEL_PROVIDER=mock` genuinely demoable and CI-safe. It holds
the same seed rows as `seed.sql`, so a test that passes here is testing the same
scenario it would test against Postgres.
"""

from __future__ import annotations

import copy
from datetime import date, timedelta
from typing import Any

# ORD-1005 is dated relative to today so the "small, recent, in-policy" refund
# stays auto-approvable forever. A fixed date would quietly fall outside the
# 30-day window and the auto-execute path would stop being demonstrable.
_RECENT_DELIVERY = (date.today() - timedelta(days=5)).isoformat()
_RECENT_PLACED = (date.today() - timedelta(days=10)).isoformat()

from app.db.base import (
    AuditEntry,
    EscalationRecord,
    OrderRecord,
    PolicyRecord,
    ProductRecord,
    RefundRecord,
    Store,
)

# Mirrors db/seed.sql. Keep the two in step: the demo scenarios depend on these
# specific orders existing with these specific statuses.
SEED_ORDERS: list[OrderRecord] = [
    OrderRecord(
        order_id="ORD-1001",
        business_id="biz_demo",
        customer_email="ayesha.k@example.com",
        customer_name="Ayesha K.",
        status="delivered",
        placed_at="2026-06-28",
        carrier="DHL Express",
        tracking_number="DHL7742119003",
        eta="2026-07-02",
        item_count=1,
        total="149.00",
    ),
    OrderRecord(
        order_id="ORD-1002",
        business_id="biz_demo",
        customer_email="ayesha.k@example.com",
        customer_name="Ayesha K.",
        status="in_transit",
        placed_at="2026-07-19",
        carrier="FedEx",
        tracking_number="FX884120774",
        eta="2026-07-29",
        item_count=2,
        total="59.00",
    ),
    OrderRecord(
        order_id="ORD-1003",
        business_id="biz_demo",
        customer_email="daniel.m@example.com",
        customer_name="Daniel M.",
        status="delivered",
        placed_at="2026-04-11",
        carrier="DHL Express",
        tracking_number="DHL7740028851",
        eta="2026-04-16",
        item_count=1,
        total="89.00",
    ),
    OrderRecord(
        order_id="ORD-1004",
        business_id="biz_demo",
        customer_email="sofia.r@example.com",
        customer_name="Sofia R.",
        status="processing",
        placed_at="2026-07-24",
        carrier=None,
        tracking_number=None,
        eta="2026-08-01",
        item_count=3,
        total="420.00",
    ),
    # Small, recent and in policy: the only order that can be refunded without a
    # human. Every other seeded order exceeds the £25 auto-cap or falls outside
    # the refund window, so without this the auto-execute path is unreachable.
    OrderRecord(
        order_id="ORD-1005",
        business_id="biz_demo",
        customer_email="ayesha.k@example.com",
        customer_name="Ayesha K.",
        status="delivered",
        placed_at=_RECENT_PLACED,
        carrier="Royal Mail",
        tracking_number="RM4471200GB",
        eta=_RECENT_DELIVERY,
        item_count=1,
        total="19.99",
    ),
    # A second tenant. Exists so cross-tenant isolation is actually testable
    # rather than merely asserted.
    OrderRecord(
        order_id="ORD-1002",
        business_id="biz_other",
        customer_email="someone@other.example.com",
        customer_name="Other Tenant Customer",
        status="cancelled",
        placed_at="2026-07-01",
        carrier=None,
        tracking_number=None,
        eta=None,
        item_count=1,
        total="10.00",
    ),
]


# Two desks and two seating options, so "compare these" has a real answer.
# PRD-TRAY-1 is deliberately out of stock — an availability state the UI must handle.
SEED_PRODUCTS: list[ProductRecord] = [
    ProductRecord(
        product_id="PRD-DESK-1",
        business_id="biz_demo",
        name="AeroDesk Pro Standing Desk",
        price="149.00",
        stock=12,
        summary="Electric sit-stand desk with a memory controller and a solid bamboo top.",
        attributes={
            "height_range": "71-121 cm",
            "top_material": "Bamboo",
            "weight_capacity": "80 kg",
            "adjustment": "Electric, 4 memory presets",
            "warranty": "5 years",
            "assembly": "About 25 minutes",
        },
    ),
    ProductRecord(
        product_id="PRD-DESK-2",
        business_id="biz_demo",
        name="AeroDesk Lite Standing Desk",
        price="99.00",
        stock=30,
        summary="Manual crank sit-stand desk in a compact footprint for smaller rooms.",
        attributes={
            "height_range": "73-118 cm",
            "top_material": "Laminate",
            "weight_capacity": "60 kg",
            "adjustment": "Manual crank",
            "warranty": "2 years",
            "assembly": "About 40 minutes",
        },
    ),
    ProductRecord(
        product_id="PRD-CHAIR-1",
        business_id="biz_demo",
        name="AeroChair Ergonomic Task Chair",
        price="249.00",
        stock=5,
        summary="Mesh-back task chair with adjustable lumbar support and a headrest.",
        attributes={
            "back": "Breathable mesh",
            "lumbar": "Adjustable, 4-way",
            "armrests": "3D adjustable",
            "weight_capacity": "120 kg",
            "warranty": "5 years",
        },
    ),
    ProductRecord(
        product_id="PRD-CUSH-1",
        business_id="biz_demo",
        name="AeroChair Lumbar Cushion",
        price="29.50",
        stock=80,
        summary="Memory-foam lumbar cushion that straps to most existing office chairs.",
        attributes={
            "fill": "Memory foam",
            "cover": "Washable mesh",
            "fitting": "Two-strap, fits most chairs",
            "warranty": "1 year",
        },
    ),
    ProductRecord(
        product_id="PRD-TRAY-1",
        business_id="biz_demo",
        name="AeroDesk Cable Tray",
        price="140.00",
        stock=0,
        summary="Under-desk cable management tray. Currently out of stock.",
        attributes={
            "length": "80 cm",
            "mounting": "Clamp-on, no drilling",
            "warranty": "2 years",
        },
    ),
    ProductRecord(
        product_id="PRD-OTHER-1",
        business_id="biz_other",
        name="Unrelated Seller Widget",
        price="10.00",
        stock=3,
        summary="Belongs to another tenant and must never surface for biz_demo.",
        attributes={"note": "tenancy fixture"},
    ),
]

# Parsed passages of the seller's written policy. Every one carries a source_ref;
# Phase 4's grounding guardrail refuses any answer that cannot cite one.
SEED_POLICIES: list[PolicyRecord] = [
    PolicyRecord(
        business_id="biz_demo",
        topic="Refund window",
        text=(
            "Refunds are available within 30 days of delivery, provided the item is "
            "unused and in its original packaging. Refunds are issued to the original "
            "payment method and take 5-10 business days to appear."
        ),
        source_ref="refund-policy.md#refund-window",
    ),
    PolicyRecord(
        business_id="biz_demo",
        topic="Damaged or faulty goods",
        text=(
            "If an item arrives damaged or develops a fault within 30 days, we replace "
            "or refund it in full including original shipping. Photographs of the damage "
            "help us process the claim faster, but are not required."
        ),
        source_ref="refund-policy.md#damaged-goods",
    ),
    PolicyRecord(
        business_id="biz_demo",
        topic="How to start a return",
        text=(
            "To return an item, contact support with your order number. We email a "
            "prepaid return label. Returns are free for faulty goods; for change-of-mind "
            "returns a 4.99 label fee is deducted from the refund."
        ),
        source_ref="returns-policy.md#starting-a-return",
    ),
    PolicyRecord(
        business_id="biz_demo",
        topic="Order processing and dispatch",
        text=(
            "Orders placed before 2pm on a working day are dispatched the same day. "
            "Orders placed after 2pm, at weekends, or on public holidays are dispatched "
            "the next working day."
        ),
        source_ref="shipping-policy.md#dispatch",
    ),
    PolicyRecord(
        business_id="biz_demo",
        topic="Delivery times and methods",
        text=(
            "Standard delivery takes 3-5 working days and is free over 50. Express "
            "delivery takes 1-2 working days and costs 7.99. Large items such as desks "
            "are delivered by a two-person carrier team on a booked slot."
        ),
        source_ref="shipping-policy.md#delivery-times",
    ),
    PolicyRecord(
        business_id="biz_demo",
        topic="Warranty cover",
        text=(
            "Desks and chairs carry a 5 year warranty on frames and mechanisms. "
            "Accessories carry 1-2 years. Warranty covers manufacturing defects, not "
            "accidental damage or normal wear."
        ),
        source_ref="warranty-policy.md#cover",
    ),
    PolicyRecord(
        business_id="biz_other",
        topic="Unrelated seller policy",
        text="Belongs to another tenant and must never surface for biz_demo.",
        source_ref="other-tenant.md#fixture",
    ),
]


class MockStore(Store):
    kind = "mock"

    def __init__(self) -> None:
        self._orders: dict[tuple[str, str], OrderRecord] = {
            (o.business_id, o.order_id): o for o in SEED_ORDERS
        }
        self._products = list(SEED_PRODUCTS)
        self._policies = list(SEED_POLICIES)
        self._audit: list[AuditEntry] = []
        self._sessions: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._refunds: dict[tuple[str, str], RefundRecord] = {}
        self._escalations: dict[tuple[str, str], EscalationRecord] = {}

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def health(self) -> bool:
        return True

    async def get_order(self, business_id: str, order_id: str) -> OrderRecord | None:
        return self._orders.get((business_id, order_id))

    # Sort order matches the Postgres store's ORDER BY exactly. This is not
    # cosmetic: `keyword.rank` breaks score ties by list position, so if the two
    # stores returned different orders they could resolve a tie differently and
    # the "identical behaviour on either store" guarantee would be a fiction.

    async def list_products(self, business_id: str) -> list[ProductRecord]:
        return sorted(
            (p for p in self._products if p.business_id == business_id),
            key=lambda p: p.product_id,
        )

    async def list_policies(self, business_id: str) -> list[PolicyRecord]:
        return sorted(
            (p for p in self._policies if p.business_id == business_id),
            key=lambda p: p.source_ref,
        )

    async def create_refund(self, record: RefundRecord) -> bool:
        key = (record.business_id, record.order_id)
        if key in self._refunds:
            return False
        self._refunds[key] = record
        return True

    async def get_refund(self, business_id: str, order_id: str) -> RefundRecord | None:
        return self._refunds.get((business_id, order_id))

    async def create_escalation(self, record: EscalationRecord) -> None:
        self._escalations[(record.business_id, record.escalation_id)] = record

    async def list_escalations(
        self, business_id: str, status: str | None = None, limit: int = 50
    ) -> list[EscalationRecord]:
        rows = [
            e
            for (biz, _), e in self._escalations.items()
            if biz == business_id and (status is None or e.status == status)
        ]
        rows.sort(key=lambda e: e.created_at, reverse=True)
        return rows[:limit]

    async def get_escalation(
        self, business_id: str, escalation_id: str
    ) -> EscalationRecord | None:
        return self._escalations.get((business_id, escalation_id))

    async def resolve_escalation(
        self,
        business_id: str,
        escalation_id: str,
        status: str,
        resolved_by: str,
        reason: str | None = None,
    ) -> bool:
        record = self._escalations.get((business_id, escalation_id))
        if record is None or record.status != "pending":
            return False
        record.status = status
        record.resolved_by = resolved_by
        record.resolution_reason = reason
        return True

    async def write_audit(self, entry: AuditEntry) -> None:
        self._audit.append(entry)

    async def recent_audit(self, business_id: str, limit: int = 20) -> list[AuditEntry]:
        rows = [e for e in self._audit if e.business_id == business_id]
        return list(reversed(rows))[:limit]

    async def get_session_items(
        self, business_id: str, session_id: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        items = self._sessions.get((business_id, session_id), [])
        selected = items if limit is None else items[-limit:]
        # Copy so a caller mutating the result cannot corrupt stored memory.
        return copy.deepcopy(selected)

    async def add_session_items(
        self, business_id: str, session_id: str, items: list[dict[str, Any]]
    ) -> None:
        if not items:
            return
        bucket = self._sessions.setdefault((business_id, session_id), [])
        bucket.extend(copy.deepcopy(items))

    async def pop_session_item(
        self, business_id: str, session_id: str
    ) -> dict[str, Any] | None:
        bucket = self._sessions.get((business_id, session_id))
        if not bucket:
            return None
        return bucket.pop()

    async def clear_session(self, business_id: str, session_id: str) -> None:
        self._sessions.pop((business_id, session_id), None)
