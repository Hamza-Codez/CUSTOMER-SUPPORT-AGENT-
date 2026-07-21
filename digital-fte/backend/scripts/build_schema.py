"""Concatenate the numbered migrations into a single db/schema.sql.

Setting up a fresh Supabase project should be one paste, not four. The numbered
migrations stay the source of truth; this is a generated convenience file, and
`tests/test_schema.py` fails if it drifts out of sync.

    python scripts/build_schema.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS = BACKEND_DIR / "db" / "migrations"
SCHEMA = BACKEND_DIR / "db" / "schema.sql"

HEADER = """-- GENERATED FILE — do not edit.
-- Built from db/migrations/ by scripts/build_schema.py.
--
-- Paste the whole thing into the Supabase SQL Editor and run it once. It is
-- idempotent: every statement is CREATE IF NOT EXISTS / CREATE OR REPLACE /
-- ON CONFLICT, so re-running is safe.
"""


def build() -> str:
    parts = [HEADER]
    for path in sorted(MIGRATIONS.glob("*.sql")):
        parts.append(f"\n\n-- ==========================================================\n"
                     f"-- {path.name}\n"
                     f"-- ==========================================================\n")
        parts.append(path.read_text(encoding="utf-8").strip())
    return "".join(parts) + "\n"


if __name__ == "__main__":
    SCHEMA.write_text(build(), encoding="utf-8")
    count = len(list(MIGRATIONS.glob("*.sql")))
    print(f"Wrote {SCHEMA.relative_to(BACKEND_DIR)} from {count} migrations.")
    sys.exit(0)
