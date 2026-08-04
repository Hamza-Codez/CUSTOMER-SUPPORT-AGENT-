"""Hybrid retrieval — the single way policy passages are found.

Two signals, combined deliberately:

**Keyword** (`keyword.py`) is precise and, importantly, *knows when it has
nothing*. Its IDF weighting and title boost were tuned against this corpus and
score 13/13 on a fixed set that includes questions the documents do not answer.

**Vector** adds recall. It reaches phrasings that share no words with the text —
the thing keyword search structurally cannot do.

Admission is `keyword OR vector`, and that asymmetry is the whole design:

- Keyword alone would reject a customer who says "I'd like my cash returned"
  when the policy says "refund", because no term matches.
- Vector alone cannot be trusted to reject. Measured against Gemini embeddings,
  the right passage scored 0.645 while "the capital of France" scored 0.453 —
  a 0.19 band with no clean gap. Nearest-neighbour search always returns a
  nearest neighbour; on its own it can only ever answer.

So each signal covers the other's failure, and either one can admit a passage —
but only above a floor it has actually been measured against.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.db.base import PolicyRecord
from app.adapters import DataAdapter
from app.rag import keyword
from app.rag.embeddings import embed_one

# How many nearest neighbours to consider before filtering.
CANDIDATES = 6


@dataclass
class RetrievedPassage:
    record: PolicyRecord
    keyword_score: float
    vector_score: float
    admitted_by: str

    @property
    def rank_score(self) -> float:
        """Keyword leads because it is the better-calibrated signal here; vector
        breaks ties and lifts passages that match in meaning but not in words."""
        return self.keyword_score + (self.vector_score * 0.5)


def _text_of(record: PolicyRecord) -> tuple[str, str]:
    return (record.topic, record.text)


async def retrieve_policies(
    adapter: DataAdapter,
    business_id: str,
    question: str,
    limit: int = 2,
) -> list[RetrievedPassage]:
    """Best passages for a question, or an empty list when the corpus has none.

    Returning nothing is a first-class outcome, not a failure: it is what lets the
    agent say "I can't confirm that" instead of citing whatever was least
    unrelated.
    """
    settings = get_settings()
    candidates = await adapter.list_policies(business_id)
    if not candidates:
        return []

    # Keyword scores over the whole tenant corpus, unfiltered — the floor is
    # applied below so both signals are judged the same way.
    keyword_hits = {
        record.source_ref: score
        for record, score in keyword.score_all(question, candidates, text_of=_text_of)
    }

    vector_hits: dict[str, float] = {}
    if settings.retrieval_use_vectors:
        try:
            query_vector = await embed_one(question)
            vector_hits = {
                record.source_ref: similarity
                for record, similarity in await adapter.search_policies(
                    business_id, query_vector, limit=CANDIDATES
                )
            }
        except Exception:
            # Retrieval must survive an embedding outage. Keyword alone is a
            # narrower net, never a wrong one, so degrading to it is safe.
            vector_hits = {}

    results: list[RetrievedPassage] = []
    for record in candidates:
        k = keyword_hits.get(record.source_ref, 0.0)
        v = vector_hits.get(record.source_ref, 0.0)

        by_keyword = k >= keyword.MIN_RELEVANCE
        by_vector = v >= settings.retrieval_vector_floor
        if not (by_keyword or by_vector):
            continue

        results.append(
            RetrievedPassage(
                record=record,
                keyword_score=k,
                vector_score=v,
                admitted_by="keyword" if by_keyword else "vector",
            )
        )

    results.sort(key=lambda r: r.rank_score, reverse=True)
    return results[:limit]
