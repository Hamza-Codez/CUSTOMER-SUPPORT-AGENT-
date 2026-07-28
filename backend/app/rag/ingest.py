"""Ingest the seller's documents into the knowledge base.

Parse → embed → upsert, keyed by `source_ref` so re-running is safe and updates
in place. This is the one path documents take into the store, shared by the
setup scripts and the test fixtures, so a passage can never differ between how
it was loaded for a demo and how it was loaded for a test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.db.base import PolicyRecord, Store
from app.rag.embeddings import get_embedder
from app.rag.parser import parse_directory


@dataclass
class IngestReport:
    business_id: str
    passages: int
    embedded: bool
    provider: str
    dim: int
    source_refs: list[str]


async def ingest_knowledge_base(
    store: Store,
    business_id: str,
    directory: Path | None = None,
) -> IngestReport:
    """Load every document into one tenant's knowledge base."""
    passages = parse_directory(directory)
    if not passages:
        return IngestReport(business_id, 0, False, "none", 0, [])

    embedder = get_embedder()
    # Embed topic and body together: a question often matches the heading
    # ("refund window") more directly than any sentence beneath it.
    vectors = await embedder.embed([f"{p.topic}\n{p.text}" for p in passages])

    for passage, vector in zip(passages, vectors):
        await store.upsert_policy(
            PolicyRecord(
                business_id=business_id,
                topic=passage.topic,
                text=passage.text,
                source_ref=passage.source_ref,
                doc=passage.doc,
            ),
            vector,
        )

    return IngestReport(
        business_id=business_id,
        passages=len(passages),
        embedded=True,
        provider=embedder.name,
        dim=embedder.dim,
        source_refs=[p.source_ref for p in passages],
    )
