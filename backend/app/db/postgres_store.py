"""PostgreSQL store, via asyncpg.

Implements exactly the same `Store` interface as `MockStore`. Queries select only
the columns a caller needs — no `SELECT *` reaching the tool layer — and every
statement is filtered by `business_id`.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import asyncpg

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
    Store,
    UsageRecord,
    UsageSummary,
    UserRecord,
    VerificationRecord,
)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SEED_PATH = Path(__file__).with_name("seed.sql")

# Scoped column list. `c.email` is here because the tool needs it to verify
# identity; it is dropped before anything reaches the model.
_ORDER_SELECT = """
    select o.order_id,
           o.business_id,
           c.email                as customer_email,
           c.name                 as customer_name,
           o.status,
           o.placed_at,
           o.carrier,
           o.tracking_number,
           o.eta,
           o.total,
           coalesce((select sum(oi.qty)
                     from order_items oi
                     where oi.order_ref = o.id), 0)::int as item_count
      from orders o
      join customers c on c.id = o.customer_id
     where o.business_id = $1
       and o.order_id = $2
"""


# The operator's own view of their orders. Written out rather than derived from
# _ORDER_SELECT: a query you have to mentally string-edit to read is a query
# nobody will notice a mistake in.
_ORDER_LIST = """
    select o.order_id,
           o.business_id,
           c.email                as customer_email,
           c.name                 as customer_name,
           o.status,
           o.placed_at,
           o.carrier,
           o.tracking_number,
           o.eta,
           o.total,
           coalesce((select sum(oi.qty)
                     from fte.order_items oi
                     where oi.order_ref = o.id), 0)::int as item_count
      from fte.orders o
      join fte.customers c on c.id = o.customer_id
     where o.business_id = $1
     order by o.placed_at desc, o.order_id desc
     limit $2
"""


def _money(value: Decimal | None) -> str:
    return f"{Decimal(value or 0):.2f}"


def _date(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _vector_literal(embedding: list[float]) -> str:
    """pgvector's text input format. Sent as a string and cast in SQL, so no
    codec registration is needed for a type asyncpg does not know natively."""
    return "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"


def _policy(row: Any) -> PolicyRecord:
    return PolicyRecord(
        business_id=row["business_id"],
        topic=row["topic"],
        text=row["body"],
        source_ref=row["source_ref"],
        doc=row["doc"] or "",
    )


class PostgresStore(Store):
    kind = "postgres"

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    @staticmethod
    async def _init_connection(conn: asyncpg.Connection) -> None:
        # asyncpg hands back jsonb as raw text unless a codec is registered.
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=1,
                max_size=5,
                init=self._init_connection,
                # Our tables live in the `fte` schema, never `public` — the target
                # database may host unrelated projects with colliding table names.
                # Every unqualified identifier below resolves here first.
                server_settings={"search_path": "fte,public"},
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("PostgresStore.connect() was never awaited")
        return self._pool

    async def health(self) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("select 1")
            return True
        except Exception:
            # Health is a status report, not an error path: a down database must
            # surface as `db: down`, never as a 500 from /health.
            return False

    async def apply_schema(self, seed: bool = True) -> None:
        """Create tables and optionally load demo rows. Both files are idempotent."""
        async with self.pool.acquire() as conn:
            await conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
            if seed:
                await conn.execute(SEED_PATH.read_text(encoding="utf-8"))

    # --- records --------------------------------------------------------------

    async def get_order(self, business_id: str, order_id: str) -> OrderRecord | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(_ORDER_SELECT, business_id, order_id)
        if row is None:
            return None
        return OrderRecord(
            order_id=row["order_id"],
            business_id=row["business_id"],
            customer_email=row["customer_email"],
            customer_name=row["customer_name"],
            status=row["status"],
            placed_at=_date(row["placed_at"]) or "",
            carrier=row["carrier"],
            tracking_number=row["tracking_number"],
            eta=_date(row["eta"]),
            item_count=row["item_count"],
            total=_money(row["total"]),
        )

    async def list_orders(
        self, business_id: str, limit: int = 50
    ) -> list[OrderRecord]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(_ORDER_LIST, business_id, limit)
        return [
            OrderRecord(
                order_id=r["order_id"],
                business_id=r["business_id"],
                customer_email=r["customer_email"],
                customer_name=r["customer_name"],
                status=r["status"],
                placed_at=_date(r["placed_at"]) or "",
                carrier=r["carrier"],
                tracking_number=r["tracking_number"],
                eta=_date(r["eta"]),
                item_count=r["item_count"],
                total=_money(r["total"]),
            )
            for r in rows
        ]

    async def list_products(self, business_id: str) -> list[ProductRecord]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select product_id, business_id, name, price, stock, summary, attributes
                  from fte.products
                 where business_id = $1
                 order by product_id
                """,
                business_id,
            )
        return [
            ProductRecord(
                product_id=r["product_id"],
                business_id=r["business_id"],
                name=r["name"],
                price=_money(r["price"]),
                stock=r["stock"],
                summary=r["summary"],
                attributes=dict(r["attributes"] or {}),
            )
            for r in rows
        ]

    async def list_policies(self, business_id: str) -> list[PolicyRecord]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select business_id, doc, topic, body, source_ref
                  from fte.policies
                 where business_id = $1
                 order by source_ref
                """,
                business_id,
            )
        return [_policy(r) for r in rows]

    async def search_policies(
        self, business_id: str, embedding: list[float], limit: int = 5
    ) -> list[tuple[PolicyRecord, float]]:
        # `<=>` is cosine *distance*; 1 - distance gives similarity, so callers
        # everywhere read "higher is better". Rows without an embedding are
        # excluded rather than ranked as maximally distant, which would put
        # un-ingested passages at the bottom of every result set as if they had
        # been considered.
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select business_id, doc, topic, body, source_ref,
                       1 - (embedding <=> $2::vector) as similarity
                  from fte.policies
                 where business_id = $1
                   and embedding is not null
                 order by embedding <=> $2::vector
                 limit $3
                """,
                business_id,
                _vector_literal(embedding),
                limit,
            )
        return [(_policy(r), float(r["similarity"])) for r in rows]

    async def upsert_policy(
        self, record: PolicyRecord, embedding: list[float] | None
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                insert into fte.policies
                    (business_id, doc, topic, body, source_ref, embedding)
                values ($1, $2, $3, $4, $5, $6::vector)
                on conflict (business_id, source_ref) do update
                    set doc = excluded.doc,
                        topic = excluded.topic,
                        body = excluded.body,
                        embedding = excluded.embedding
                """,
                record.business_id,
                record.doc,
                record.topic,
                record.text,
                record.source_ref,
                _vector_literal(embedding) if embedding is not None else None,
            )

    # --- money and escalations -------------------------------------------------

    async def create_refund(self, record: RefundRecord) -> bool:
        async with self.pool.acquire() as conn:
            # ON CONFLICT DO NOTHING turns the unique constraint into an answer
            # rather than an exception: the caller learns this order was already
            # refunded and can say so, instead of the run blowing up.
            row = await conn.fetchrow(
                """
                insert into fte.refunds
                    (refund_id, business_id, order_id, amount, reason, status, approved_by)
                values ($1, $2, $3, $4, $5, $6, $7)
                on conflict (business_id, order_id) do nothing
                returning refund_id
                """,
                record.refund_id,
                record.business_id,
                record.order_id,
                Decimal(record.amount),
                record.reason,
                record.status,
                record.approved_by,
            )
        return row is not None

    async def get_refund(self, business_id: str, order_id: str) -> RefundRecord | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select refund_id, business_id, order_id, amount, reason, status, approved_by
                  from fte.refunds
                 where business_id = $1 and order_id = $2
                """,
                business_id,
                order_id,
            )
        if row is None:
            return None
        return RefundRecord(
            refund_id=row["refund_id"],
            business_id=row["business_id"],
            order_id=row["order_id"],
            amount=_money(row["amount"]),
            reason=row["reason"],
            status=row["status"],
            approved_by=row["approved_by"],
        )

    async def create_escalation(self, record: EscalationRecord) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                insert into fte.escalations
                    (escalation_id, business_id, session_id, status,
                     decision_card, run_state, created_at)
                values ($1, $2, $3, $4, $5, $6, $7)
                """,
                record.escalation_id,
                record.business_id,
                record.session_id,
                record.status,
                record.decision_card,
                record.run_state,
                record.created_at,
            )

    def _escalation(self, row: Any) -> EscalationRecord:
        return EscalationRecord(
            escalation_id=row["escalation_id"],
            business_id=row["business_id"],
            session_id=row["session_id"],
            status=row["status"],
            decision_card=row["decision_card"] or {},
            run_state=row["run_state"],
            resolved_by=row["resolved_by"],
            resolution_reason=row["resolution_reason"],
            created_at=row["created_at"],
        )

    _ESCALATION_COLS = """
        escalation_id, business_id, session_id, status, decision_card,
        run_state, resolved_by, resolution_reason, created_at
    """

    async def list_escalations(
        self, business_id: str, status: str | None = None, limit: int = 50
    ) -> list[EscalationRecord]:
        async with self.pool.acquire() as conn:
            if status is None:
                rows = await conn.fetch(
                    f"""
                    select {self._ESCALATION_COLS} from fte.escalations
                     where business_id = $1
                     order by created_at desc, id desc
                     limit $2
                    """,
                    business_id,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    f"""
                    select {self._ESCALATION_COLS} from fte.escalations
                     where business_id = $1 and status = $2
                     order by created_at desc, id desc
                     limit $3
                    """,
                    business_id,
                    status,
                    limit,
                )
        return [self._escalation(r) for r in rows]

    async def get_escalation(
        self, business_id: str, escalation_id: str
    ) -> EscalationRecord | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                select {self._ESCALATION_COLS} from fte.escalations
                 where business_id = $1 and escalation_id = $2
                """,
                business_id,
                escalation_id,
            )
        return self._escalation(row) if row else None

    async def resolve_escalation(
        self,
        business_id: str,
        escalation_id: str,
        status: str,
        resolved_by: str,
        reason: str | None = None,
    ) -> bool:
        async with self.pool.acquire() as conn:
            # `and status = 'pending'` makes this a compare-and-set: two operators
            # clicking Approve at once, only one wins, and only one refund happens.
            row = await conn.fetchrow(
                """
                update fte.escalations
                   set status = $3, resolved_by = $4, resolution_reason = $5
                 where business_id = $1
                   and escalation_id = $2
                   and status = 'pending'
                returning escalation_id
                """,
                business_id,
                escalation_id,
                status,
                resolved_by,
                reason,
            )
        return row is not None

    # --- verified identity (session-scoped) -------------------------------------

    async def add_verification(self, record: VerificationRecord) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                insert into fte.session_verifications
                    (business_id, session_id, order_id, email, name, verified_at)
                values ($1, $2, $3, $4, $5, $6)
                on conflict (business_id, session_id, order_id) do update
                    set email = excluded.email,
                        name = excluded.name,
                        verified_at = excluded.verified_at
                """,
                record.business_id,
                record.session_id,
                record.order_id,
                record.email,
                record.name,
                record.verified_at,
            )

    async def get_verifications(
        self, business_id: str, session_id: str
    ) -> list[VerificationRecord]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select business_id, session_id, order_id, email, name, verified_at
                  from fte.session_verifications
                 where business_id = $1 and session_id = $2
                 order by verified_at
                """,
                business_id,
                session_id,
            )
        return [
            VerificationRecord(
                business_id=r["business_id"],
                session_id=r["session_id"],
                order_id=r["order_id"],
                email=r["email"],
                name=r["name"],
                verified_at=r["verified_at"],
            )
            for r in rows
        ]

    # --- email and feedback -----------------------------------------------------

    _EMAIL_COLS = """
        email_id, business_id, session_id, recipient, subject, body_html,
        feedback_token, status, provider, error, created_at
    """

    def _email(self, row: Any) -> EmailRecord:
        return EmailRecord(
            email_id=row["email_id"],
            business_id=row["business_id"],
            session_id=row["session_id"],
            recipient=row["recipient"],
            subject=row["subject"],
            body_html=row["body_html"],
            feedback_token=row["feedback_token"],
            status=row["status"],
            provider=row["provider"],
            error=row["error"],
            created_at=row["created_at"],
        )

    async def create_email(self, record: EmailRecord) -> bool:
        async with self.pool.acquire() as conn:
            # The unique (business_id, session_id) turns "already emailed" into an
            # answer rather than an exception.
            row = await conn.fetchrow(
                """
                insert into fte.emails
                    (email_id, business_id, session_id, recipient, subject,
                     body_html, feedback_token, status, provider, error, created_at)
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                on conflict (business_id, session_id) do nothing
                returning email_id
                """,
                record.email_id,
                record.business_id,
                record.session_id,
                record.recipient,
                record.subject,
                record.body_html,
                record.feedback_token,
                record.status,
                record.provider,
                record.error,
                record.created_at,
            )
        return row is not None

    async def update_email_status(
        self, business_id: str, email_id: str, status: str, error: str | None = None
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                update fte.emails set status = $3, error = $4
                 where business_id = $1 and email_id = $2
                """,
                business_id,
                email_id,
                status,
                error,
            )

    async def get_email_by_token(self, feedback_token: str) -> EmailRecord | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"select {self._EMAIL_COLS} from fte.emails where feedback_token = $1",
                feedback_token,
            )
        return self._email(row) if row else None

    async def get_email_for_session(
        self, business_id: str, session_id: str
    ) -> EmailRecord | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                select {self._EMAIL_COLS} from fte.emails
                 where business_id = $1 and session_id = $2
                """,
                business_id,
                session_id,
            )
        return self._email(row) if row else None

    async def record_feedback(self, record: FeedbackRecord) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                insert into fte.feedback
                    (business_id, feedback_token, session_id, rating, comment, created_at)
                values ($1, $2, $3, $4, $5, $6)
                on conflict (feedback_token) do nothing
                returning id
                """,
                record.business_id,
                record.feedback_token,
                record.session_id,
                record.rating,
                record.comment,
                record.created_at,
            )
        return row is not None

    async def list_feedback(
        self, business_id: str, limit: int = 50
    ) -> list[FeedbackRecord]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select business_id, feedback_token, session_id, rating, comment, created_at
                  from fte.feedback
                 where business_id = $1
                 order by created_at desc, id desc
                 limit $2
                """,
                business_id,
                limit,
            )
        return [
            FeedbackRecord(
                business_id=r["business_id"],
                feedback_token=r["feedback_token"],
                session_id=r["session_id"],
                rating=r["rating"],
                comment=r["comment"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # --- accounts ---------------------------------------------------------------

    async def create_business(self, business_id: str, name: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                insert into fte.businesses (id, name) values ($1, $2)
                on conflict (id) do nothing
                """,
                business_id,
                name,
            )

    async def create_user(self, record: UserRecord) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                insert into fte.users
                    (user_id, business_id, email, name, password_hash, role, created_at)
                values ($1, $2, lower($3), $4, $5, $6, $7)
                on conflict (email) do nothing
                returning user_id
                """,
                record.user_id,
                record.business_id,
                record.email,
                record.name,
                record.password_hash,
                record.role,
                record.created_at,
            )
        return row is not None

    async def get_business_name(self, business_id: str) -> str | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "select name from fte.businesses where id = $1", business_id
            )

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select user_id, business_id, email, name, password_hash, role, created_at
                  from fte.users where email = lower($1)
                """,
                email,
            )
        if row is None:
            return None
        return UserRecord(
            user_id=row["user_id"],
            business_id=row["business_id"],
            email=row["email"],
            name=row["name"],
            password_hash=row["password_hash"],
            role=row["role"],
            created_at=row["created_at"],
        )

    # --- commercial -------------------------------------------------------------

    _INTEGRATION_COLS = """
        request_id, business_id, contact_name, contact_email, website, platform,
        monthly_conversations, notes, status, created_at
    """

    async def create_integration_request(self, record: IntegrationRequest) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"""
                insert into fte.integration_requests ({self._INTEGRATION_COLS})
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                record.request_id,
                record.business_id,
                record.contact_name,
                record.contact_email,
                record.website,
                record.platform,
                record.monthly_conversations,
                record.notes,
                record.status,
                record.created_at,
            )

    async def list_integration_requests(
        self, business_id: str, limit: int = 50
    ) -> list[IntegrationRequest]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                select {self._INTEGRATION_COLS} from fte.integration_requests
                 where business_id = $1
                 order by created_at desc, id desc
                 limit $2
                """,
                business_id,
                limit,
            )
        return [
            IntegrationRequest(
                request_id=r["request_id"],
                business_id=r["business_id"],
                contact_name=r["contact_name"],
                contact_email=r["contact_email"],
                website=r["website"],
                platform=r["platform"],
                monthly_conversations=r["monthly_conversations"],
                notes=r["notes"],
                status=r["status"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def record_usage(self, record: UsageRecord) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                insert into fte.conversation_usage
                    (business_id, session_id, provider, model, requests,
                     input_tokens, output_tokens, ts)
                values ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                record.business_id,
                record.session_id,
                record.provider,
                record.model,
                record.requests,
                record.input_tokens,
                record.output_tokens,
                record.ts,
            )

    async def usage_summary(self, business_id: str) -> UsageSummary:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select count(distinct session_id)::int    as conversations,
                       coalesce(sum(requests), 0)::int    as model_requests,
                       coalesce(sum(input_tokens), 0)::int  as input_tokens,
                       coalesce(sum(output_tokens), 0)::int as output_tokens,
                       coalesce(array_agg(distinct provider), '{}') as providers
                  from fte.conversation_usage
                 where business_id = $1
                """,
                business_id,
            )
        return UsageSummary(
            conversations=row["conversations"],
            model_requests=row["model_requests"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            providers=set(row["providers"] or []),
        )

    async def conversation_count(self, business_id: str) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                select count(distinct session_id)::int
                  from fte.messages where business_id = $1
                """,
                business_id,
            ) or 0

    async def escalation_counts(self, business_id: str) -> dict[str, int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select status, count(*)::int as n
                  from fte.escalations where business_id = $1
                 group by status
                """,
                business_id,
            )
            sessions = await conn.fetchval(
                """
                select count(distinct session_id)::int
                  from fte.escalations where business_id = $1
                """,
                business_id,
            )
        counts = {"pending": 0, "approved": 0, "declined": 0}
        for row in rows:
            counts[row["status"]] = row["n"]
        counts["sessions"] = sessions or 0
        return counts

    # --- audit ----------------------------------------------------------------

    async def write_audit(self, entry: AuditEntry) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                insert into audit_logs
                    (business_id, actor, action, target, outcome, detail, ts)
                values ($1, $2, $3, $4, $5, $6, $7)
                """,
                entry.business_id,
                entry.actor,
                entry.action,
                entry.target,
                entry.outcome,
                entry.detail,
                entry.ts,
            )

    async def recent_audit(self, business_id: str, limit: int = 20) -> list[AuditEntry]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select business_id, actor, action, target, outcome, detail, ts
                  from audit_logs
                 where business_id = $1
                 order by ts desc, id desc
                 limit $2
                """,
                business_id,
                limit,
            )
        return [
            AuditEntry(
                business_id=r["business_id"],
                actor=r["actor"],
                action=r["action"],
                target=r["target"],
                outcome=r["outcome"],
                detail=r["detail"] or {},
                ts=r["ts"],
            )
            for r in rows
        ]

    # --- agent session memory -------------------------------------------------

    async def get_session_items(
        self, business_id: str, session_id: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            if limit is None:
                rows = await conn.fetch(
                    """
                    select item from messages
                     where business_id = $1 and session_id = $2
                     order by id asc
                    """,
                    business_id,
                    session_id,
                )
            else:
                # Take the newest N, then flip back to chronological order so the
                # agent always reads history oldest-first.
                rows = await conn.fetch(
                    """
                    select item from (
                        select item, id from messages
                         where business_id = $1 and session_id = $2
                         order by id desc
                         limit $3
                    ) recent
                    order by recent.id asc
                    """,
                    business_id,
                    session_id,
                    limit,
                )
        return [r["item"] for r in rows]

    async def add_session_items(
        self, business_id: str, session_id: str, items: list[dict[str, Any]]
    ) -> None:
        if not items:
            return
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                insert into messages (business_id, session_id, role, item)
                values ($1, $2, $3, $4)
                """,
                [
                    (business_id, session_id, item.get("role"), item)
                    for item in items
                ],
            )

    async def pop_session_item(
        self, business_id: str, session_id: str
    ) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                delete from messages
                 where id = (
                    select id from messages
                     where business_id = $1 and session_id = $2
                     order by id desc
                     limit 1
                 )
                returning item
                """,
                business_id,
                session_id,
            )
        return row["item"] if row else None

    async def clear_session(self, business_id: str, session_id: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "delete from messages where business_id = $1 and session_id = $2",
                business_id,
                session_id,
            )
