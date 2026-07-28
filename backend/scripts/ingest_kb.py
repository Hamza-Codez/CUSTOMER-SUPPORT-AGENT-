"""Parse, embed and load the knowledge base into the configured store.

    uv run python scripts/ingest_kb.py

Re-runnable: passages are keyed by source_ref and updated in place. Run it again
after editing a document in app/db/knowledge/, or after changing
EMBEDDING_PROVIDER or EMBEDDING_DIM — vectors from one model mean nothing to
another.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db import build_store  # noqa: E402
from app.rag.ingest import ingest_knowledge_base  # noqa: E402

BUSINESSES = ["biz_demo"]


async def main() -> int:
    settings = get_settings()
    store = build_store()
    print(f"store={store.kind}  embeddings={settings.embedding_provider}"
          f"  model={settings.embedding_model}  dim={settings.embedding_dim}")

    try:
        await store.connect()
    except Exception as exc:
        print(f"Could not connect: {type(exc).__name__}: {exc}")
        return 2

    try:
        for business_id in BUSINESSES:
            report = await ingest_knowledge_base(store, business_id)
            if not report.passages:
                print("No documents found in app/db/knowledge/ — nothing ingested.")
                return 1
            print(f"\n{business_id}: {report.passages} passages embedded")
            for ref in report.source_refs:
                print(f"  {ref}")
        return 0
    finally:
        await store.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
