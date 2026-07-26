"""Apply the schema and load demo rows against the configured DATABASE_URL.

    uv run python scripts/init_db.py

Both SQL files are idempotent, so this is safe to re-run.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.postgres_store import PostgresStore  # noqa: E402


async def main() -> int:
    settings = get_settings()
    if not settings.database_url.strip():
        print("DATABASE_URL is empty in backend/.env — nothing to initialise.")
        print("The app runs on the in-memory store until you set one.")
        return 1

    store = PostgresStore(settings.database_url)
    try:
        await store.connect()
    except Exception as exc:
        print(f"Could not connect: {type(exc).__name__}: {exc}")
        return 2

    try:
        await store.apply_schema(seed=True)
        orders = [
            await store.get_order("biz_demo", oid)
            for oid in ("ORD-1001", "ORD-1002", "ORD-1003", "ORD-1004")
        ]
        print("Schema applied and demo data seeded.")
        for order in orders:
            if order:
                print(f"  {order.order_id}  {order.status:<11} {order.item_count} item(s)  {order.total}")
        return 0
    finally:
        await store.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
