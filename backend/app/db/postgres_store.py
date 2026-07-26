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

from app.db.base import AuditEntry, OrderRecord, Store

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
