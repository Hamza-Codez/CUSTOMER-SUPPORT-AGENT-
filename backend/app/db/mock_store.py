"""In-memory store: the zero-setup path.

This is what makes `MODEL_PROVIDER=mock` genuinely demoable and CI-safe. It holds
the same seed rows as `seed.sql`, so a test that passes here is testing the same
scenario it would test against Postgres.
"""

from __future__ import annotations

import copy
from typing import Any

from app.db.base import AuditEntry, OrderRecord, Store

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


class MockStore(Store):
    kind = "mock"

    def __init__(self) -> None:
        self._orders: dict[tuple[str, str], OrderRecord] = {
            (o.business_id, o.order_id): o for o in SEED_ORDERS
        }
        self._audit: list[AuditEntry] = []
        self._sessions: dict[tuple[str, str], list[dict[str, Any]]] = {}

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def health(self) -> bool:
        return True

    async def get_order(self, business_id: str, order_id: str) -> OrderRecord | None:
        return self._orders.get((business_id, order_id))

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
