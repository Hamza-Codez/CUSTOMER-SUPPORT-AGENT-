"""db/schema.sql is generated — this fails if it drifts from the migrations.

A stale schema.sql is worse than none: someone pastes it into a fresh project
and gets a database that is subtly behind the code.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

import build_schema  # noqa: E402

SCHEMA = BACKEND_DIR / "db" / "schema.sql"


def test_schema_sql_is_in_sync_with_the_migrations():
    """If this fails, run: python scripts/build_schema.py"""
    assert SCHEMA.is_file(), "db/schema.sql is missing — run scripts/build_schema.py"
    assert SCHEMA.read_text(encoding="utf-8") == build_schema.build(), (
        "db/schema.sql is stale. Run: python scripts/build_schema.py"
    )


def test_schema_covers_every_table_the_store_uses():
    sql = SCHEMA.read_text(encoding="utf-8").lower()
    for table in ("orders", "tickets", "kb_docs", "sessions"):
        assert f"create table if not exists {table}" in sql, f"{table} missing"
    assert "match_kb_docs" in sql          # the pgvector RPC
    assert "seed_demo_orders" in sql       # onboarding
    assert "create extension if not exists vector" in sql
