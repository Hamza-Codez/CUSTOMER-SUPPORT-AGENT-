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
    EscalationRecord,
    OrderRecord,
    PolicyRecord,
    ProductRecord,
    RefundRecord,
    Store,
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


def _money(value: Decimal | None) -> str:
    return f"{Decimal(value or 0):.2f}"


def _date(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


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
                select business_id, topic, body, source_ref
                  from fte.policies
                 where business_id = $1
                 order by source_ref
                """,
                business_id,
            )
        return [
            PolicyRecord(
                business_id=r["business_id"],
                topic=r["topic"],
                text=r["body"],
                source_ref=r["source_ref"],
            )
            for r in rows
        ]

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
