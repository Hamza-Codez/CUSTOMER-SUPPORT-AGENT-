"""Embed the knowledge base and upsert it into Supabase `kb_docs`.

    cd backend
    DATA_BACKEND=supabase EMBEDDING_PROVIDER=mock python scripts/ingest_kb.py

Source documents are `store.mock_store.KNOWLEDGE_BASE`, so both backends serve
the same content. Re-running is safe: rows upsert on `title`.

Switching EMBEDDING_PROVIDER later means re-running this — old vectors were
produced by a different model and are not comparable to new query embeddings.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402,F401  — loads .env

import embeddings                       # noqa: E402
from store import mock_store            # noqa: E402
from store import supabase_store        # noqa: E402

BATCH = 32


def main() -> int:
    docs = mock_store.KNOWLEDGE_BASE
    provider = embeddings.provider_name()
    dim = embeddings.embedding_dim()

    print(f"Embedding {len(docs)} documents with '{provider}' ({dim} dims)...")
    if provider == "mock":
        print("  note: the mock embedder is lexical, not semantic. Fine for a demo;")
        print("        set EMBEDDING_PROVIDER=openai for real semantic retrieval.")

    client = supabase_store.get_client()
    vectors = embeddings.embed([f"{d['title']} {d['body']}" for d in docs])

    rows = [{"title": d["title"], "body": d["body"], "embedding": v}
            for d, v in zip(docs, vectors)]

    for start in range(0, len(rows), BATCH):
        chunk = rows[start:start + BATCH]
        try:
            client.table("kb_docs").upsert(chunk, on_conflict="title").execute()
        except Exception as exc:
            code = getattr(exc, "code", "")
            if code in ("PGRST205", "42P01"):
                print("\nThe kb_docs table does not exist yet. Run the migrations "
                      "in the Supabase SQL Editor first:", file=sys.stderr)
                print("  db/migrations/0001_init.sql", file=sys.stderr)
                print("  db/migrations/0002_seed_orders.sql", file=sys.stderr)
                print("  db/migrations/0003_sessions.sql", file=sys.stderr)
                return 1
            raise
        print(f"  upserted {start + len(chunk)}/{len(rows)}")

    print(f"Done. kb_docs now serves {len(rows)} documents.")
    return 0


if __name__ == "__main__":
    if os.getenv("DATA_BACKEND", "mock").lower() != "supabase":
        print("Set DATA_BACKEND=supabase before ingesting.", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(main())
