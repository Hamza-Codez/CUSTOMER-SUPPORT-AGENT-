"""Apply db/schema.sql to a real Postgres — no dashboard, no copy-paste.

    python scripts/apply_schema.py

Needs one value in .env:

    SUPABASE_DB_URL=postgresql://postgres.<ref>:<password>@<host>:5432/postgres

Get it from Supabase → Project Settings → Database → Connection string → URI,
and put your database password in it. This is NOT the service key: PostgREST
(which the service key talks to) cannot run DDL, so creating tables needs a
direct Postgres connection.

The schema is idempotent — every statement is CREATE IF NOT EXISTS / CREATE OR
REPLACE / ON CONFLICT — so re-running is safe.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402,F401  — loads .env

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCHEMA = BACKEND_DIR / "db" / "schema.sql"

EXPECTED_TABLES = ("orders", "tickets", "kb_docs", "sessions")


def main() -> int:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print(__doc__, file=sys.stderr)
        print("SUPABASE_DB_URL is not set.", file=sys.stderr)
        return 1

    if not SCHEMA.is_file():
        print("db/schema.sql is missing — run: python scripts/build_schema.py",
              file=sys.stderr)
        return 1

    try:
        import psycopg
    except ImportError:
        print("psycopg is not installed: pip install 'psycopg[binary]'", file=sys.stderr)
        return 1

    sql = SCHEMA.read_text(encoding="utf-8")
    host = db_url.split("@")[-1].split("/")[0] if "@" in db_url else "the database"
    print(f"Applying db/schema.sql to {host} ...")

    try:
        with psycopg.connect(db_url, connect_timeout=15) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()

            with conn.cursor() as cur:
                cur.execute(
                    "select table_name from information_schema.tables "
                    "where table_schema = 'public' and table_name = any(%s)",
                    (list(EXPECTED_TABLES),),
                )
                found = {row[0] for row in cur.fetchall()}
    except Exception as exc:                       # noqa: BLE001 - reported, not raised
        message = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        print(f"\nFailed: {message}", file=sys.stderr)
        if "vector" in message.lower():
            print("Enable the `vector` extension: Supabase → Database → Extensions.",
                  file=sys.stderr)
        elif "password" in message.lower() or "authentication" in message.lower():
            print("Check the password inside SUPABASE_DB_URL "
                  "(Settings → Database → Reset database password).", file=sys.stderr)
        return 1

    for table in EXPECTED_TABLES:
        print(f"  {'ok  ' if table in found else 'MISS'} {table}")

    missing = set(EXPECTED_TABLES) - found
    if missing:
        print(f"\nMissing: {', '.join(sorted(missing))}", file=sys.stderr)
        return 1

    print("\nSchema applied. Next:")
    print("  python scripts/ingest_kb.py        # embed + load your documents")
    print("  python scripts/verify_supabase.py  # prove the contracts hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
