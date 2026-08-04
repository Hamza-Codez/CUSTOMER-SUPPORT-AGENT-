"""In-memory store: the zero-setup path.

This is what makes `MODEL_PROVIDER=mock` genuinely demoable and CI-safe. It holds
the same seed rows as `seed.sql`, so a test that passes here is testing the same
scenario it would test against Postgres.
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.db.base import (
    AuditEntry,
    EmailRecord,
    EscalationRecord,
    FeedbackRecord,
    IntegrationRequest,
    OrderRecord,
    PolicyRecord,
    ProductRecord,
    RefundRecord,
    SiteKeyRecord,
    Store,
    UsageRecord,
    UsageSummary,
    UserRecord,
    VerificationRecord,
    ProfileRecord,
)
from app.rag.parser import parse_directory

# ORD-1005 is dated relative to today so the "small, recent, in-policy" refund
# stays auto-approvable forever. A fixed date would quietly fall outside the
# 30-day window and the auto-execute path would stop being demonstrable.
_RECENT_DELIVERY = (date.today() - timedelta(days=5)).isoformat()
_RECENT_PLACED = (date.today() - timedelta(days=10)).isoformat()

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

def _seed_policies() -> list[PolicyRecord]:
    """Built by parsing app/db/knowledge/*.md — the same documents the Postgres
    store ingests. The knowledge base has one source, the seller's documents; a
    second copy as a Python literal would drift from them the first time someone
    edited a policy and only updated one.
    """
    records = [
        PolicyRecord(
            business_id="biz_demo",
            topic=p.topic,
            text=p.text,
            source_ref=p.source_ref,
            doc=p.doc,
        )
        for p in parse_directory()
    ]
    # A second tenant, so cross-tenant isolation is testable. Not a real document.
    records.append(
        PolicyRecord(
            business_id="biz_other",
            topic="Unrelated seller policy",
            text="Belongs to another tenant and must never surface for biz_demo.",
            source_ref="other-tenant.md#fixture",
            doc="other-tenant.md",
        )
    )
    return records


SEED_POLICIES: list[PolicyRecord] = _seed_policies()



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
        # Passage embeddings, built lazily on first search. Keyed by source_ref.
        self._policy_vectors: dict[str, list[float]] = {}
        self._refunds: dict[tuple[str, str], RefundRecord] = {}
        self._escalations: dict[tuple[str, str], EscalationRecord] = {}
        self._emails: dict[tuple[str, str], EmailRecord] = {}
        self._feedback: dict[str, FeedbackRecord] = {}
        self._verifications: dict[tuple[str, str, str], VerificationRecord] = {}
        self._users: dict[str, UserRecord] = {}
        self._profiles: dict[str, ProfileRecord] = {}
        self._site_keys: dict[str, SiteKeyRecord] = {}
        self._usage: list[UsageRecord] = []
        self._businesses: dict[str, str] = {"biz_demo": "Aeron Home Goods",
                                            "biz_other": "Unrelated Seller"}
        self._users: dict[str, UserRecord] = {}

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

    async def list_orders(
        self, business_id: str, limit: int = 50
    ) -> list[OrderRecord]:
        rows = [o for o in self._orders.values() if o.business_id == business_id]
        rows.sort(key=lambda o: (o.placed_at, o.order_id), reverse=True)
        return rows[:limit]

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

    async def search_policies(
        self, business_id: str, embedding: list[float], limit: int = 5
    ) -> list[tuple[PolicyRecord, float]]:
        """Cosine similarity in Python — the same metric Postgres computes in SQL.

        Passage embeddings are built once on first use and cached. The corpus is a
        handful of rows, so an exact scan is the right shape here as well as in
        the database.
        """
        from app.rag.embeddings import cosine, get_embedder

        candidates = await self.list_policies(business_id)
        if not candidates:
            return []

        missing = [p for p in candidates if p.source_ref not in self._policy_vectors]
        if missing:
            vectors = await get_embedder().embed(
                [f"{p.topic}\n{p.text}" for p in missing]
            )
            for record, vector in zip(missing, vectors):
                self._policy_vectors[record.source_ref] = vector

        scored = [
            (p, cosine(embedding, self._policy_vectors[p.source_ref]))
            for p in candidates
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]

    async def upsert_policy(
        self, record: PolicyRecord, embedding: list[float] | None
    ) -> None:
        self._policies = [
            p
            for p in self._policies
            if not (
                p.business_id == record.business_id
                and p.source_ref == record.source_ref
            )
        ]
        self._policies.append(record)
        if embedding is not None:
            self._policy_vectors[record.source_ref] = embedding
        else:
            self._policy_vectors.pop(record.source_ref, None)

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

    async def add_verification(self, record: VerificationRecord) -> None:
        key = (record.business_id, record.session_id, record.order_id)
        self._verifications[key] = record

    async def get_verifications(
        self, business_id: str, session_id: str
    ) -> list[VerificationRecord]:
        return [
            v
            for (biz, sess, _), v in self._verifications.items()
            if biz == business_id and sess == session_id
        ]

    async def create_email(self, record: EmailRecord) -> bool:
        key = (record.business_id, record.session_id)
        if key in self._emails:
            return False
        self._emails[key] = record
        return True

    async def update_email_status(
        self, business_id: str, email_id: str, status: str, error: str | None = None
    ) -> None:
        for record in self._emails.values():
            if record.business_id == business_id and record.email_id == email_id:
                record.status = status
                record.error = error
                return

    async def get_email_by_token(self, feedback_token: str) -> EmailRecord | None:
        for record in self._emails.values():
            if record.feedback_token == feedback_token:
                return record
        return None

    async def get_email_for_session(
        self, business_id: str, session_id: str
    ) -> EmailRecord | None:
        return self._emails.get((business_id, session_id))

    async def record_feedback(self, record: FeedbackRecord) -> bool:
        if record.feedback_token in self._feedback:
            return False
        self._feedback[record.feedback_token] = record
        return True

    async def list_feedback(
        self, business_id: str, limit: int = 50
    ) -> list[FeedbackRecord]:
        rows = [f for f in self._feedback.values() if f.business_id == business_id]
        rows.sort(key=lambda f: f.created_at, reverse=True)
        return rows[:limit]

    async def create_business(self, business_id: str, name: str) -> None:
        self._businesses[business_id] = name
        
    async def update_business_name(self, business_id: str, name: str) -> None:
        if business_id in self._businesses:
            self._businesses[business_id] = name

    async def save_profile(self, profile: ProfileRecord) -> None:
        self._profiles[profile.user_id] = profile

    async def is_profile_completed(self, user_id: str) -> bool:
        prof = self._profiles.get(user_id)
        return prof is not None and prof.status == "completed"

    async def create_user(self, record: UserRecord) -> bool:
        if record.email.casefold() in self._users:
            return False
        self._users[record.email.casefold()] = record
        return True

    async def get_business_name(self, business_id: str) -> str | None:
        return self._businesses.get(business_id)

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        return self._users.get(email.casefold())

    async def create_site_key(self, record: SiteKeyRecord) -> None:
        self._site_keys[record.key] = record

    async def get_site_key(self, key: str) -> SiteKeyRecord | None:
        return self._site_keys.get(key)

    async def list_site_keys(self, business_id: str) -> list[SiteKeyRecord]:
        rows = [k for k in self._site_keys.values() if k.business_id == business_id]
        rows.sort(key=lambda k: k.created_at, reverse=True)
        return rows

    async def revoke_site_key(self, business_id: str, key: str) -> bool:
        record = self._site_keys.get(key)
        # Scoped on the way in: one tenant must not be able to revoke another's
        # key by guessing it, and a key that is already revoked is not news.
        if record is None or record.business_id != business_id or not record.active:
            return False
        record.revoked_at = datetime.now(timezone.utc)
        return True

    async def create_integration_request(self, record: IntegrationRequest) -> None:
        self._integrations.append(record)

    async def list_integration_requests(
        self, business_id: str, limit: int = 50
    ) -> list[IntegrationRequest]:
        rows = [r for r in self._integrations if r.business_id == business_id]
        rows.sort(key=lambda r: r.created_at, reverse=True)
        return rows[:limit]

    async def record_usage(self, record: UsageRecord) -> None:
        self._usage.append(record)

    async def usage_summary(self, business_id: str) -> UsageSummary:
        rows = [u for u in self._usage if u.business_id == business_id]
        return UsageSummary(
            conversations=len({u.session_id for u in rows}),
            model_requests=sum(u.requests for u in rows),
            input_tokens=sum(u.input_tokens for u in rows),
            output_tokens=sum(u.output_tokens for u in rows),
            providers={u.provider for u in rows},
        )

    async def conversation_count(self, business_id: str) -> int:
        return len({sess for (biz, sess) in self._sessions if biz == business_id})

    async def escalation_counts(self, business_id: str) -> dict[str, int]:
        rows = [
            e for (biz, _), e in self._escalations.items() if biz == business_id
        ]
        counts = {"pending": 0, "approved": 0, "declined": 0}
        for row in rows:
            counts[row.status] = counts.get(row.status, 0) + 1
        counts["sessions"] = len({r.session_id for r in rows})
        return counts

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
