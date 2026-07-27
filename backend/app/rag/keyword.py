"""Keyword retrieval — the Phase 4 swap point.

Phase 4 replaces this with embeddings over a vector store. Until then, matching
is deliberately kept in one place and run in Python rather than pushed into SQL:
the mock and Postgres stores then rank *identically* by construction, so a demo
or a test proves the same thing on either. Policies and catalogues are small and
slow-changing, which is what makes that affordable.

Two properties matter more than ranking quality, and Phase 4 must preserve both:

1. **A miss returns nothing.** Naive overlap scoring never misses — one shared
   common word is enough — so a question about interstellar shipping to Mars
   comes back holding the damaged-goods policy, and the agent states it as fact.
   Retrieval that always answers is worse than no retrieval, because it launders
   a guess into a citation. Hence `MIN_RELEVANCE`.
2. **Common words must not decide the answer.** "Can I get my money back after
   60 days" should not match the dispatch policy just because both say "after"
   and "day". Terms are weighted by inverse document frequency, so a word that
   appears in most passages carries almost no weight.
"""

from __future__ import annotations

import math
import re
from typing import Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")

_WORD_RE = re.compile(r"[a-z0-9']+")

# The floor a match must clear to be returned at all. Tuned against the seeded
# policy set: real topical questions score well above it, and questions the
# corpus does not cover score below. Lower it and misses start returning
# confident nonsense; raise it and genuine questions go unanswered.
MIN_RELEVANCE = 0.30

# Words carrying no retrieval signal. Includes time-relative words like "after"
# and "before", which otherwise dominate any question containing a duration.
_STOPWORDS = frozenset(
    """
    a about an and any are as at be been before after but by can could do does
    did for from get got give has have how i if in into is it its me much many
    my need of on or our please so some tell that the their them then there
    these they this to want was we were what when where which who will with
    would you your
    """.split()
)

# Domain vocabulary. Customers say "money back"; the policy says "refund". Without
# this, the two never meet and the correct passage loses to an irrelevant one.
_EXPANSIONS: dict[str, set[str]] = {
    "money": {"refund"},
    "reimburse": {"refund"},
    "repay": {"refund"},
    "refund": {"refund", "return"},
    "cost": {"price"},
    "cheap": {"price"},
    "cheaper": {"price"},
    "ship": {"shipping", "delivery"},
    "shipping": {"delivery"},
    "arrive": {"delivery"},
    "arrives": {"delivery"},
    "postage": {"shipping", "delivery"},
    "broken": {"damaged", "faulty"},
    "damaged": {"damaged", "faulty"},
    "faulty": {"faulty", "damaged"},
    "guarantee": {"warranty"},
    "exchange": {"return"},
}


def tokenize(text: str) -> set[str]:
    """Lowercase word set with stopwords and one-character noise removed."""
    return {
        w
        for w in _WORD_RE.findall((text or "").lower())
        if w not in _STOPWORDS and len(w) > 1
    }


def _singularise(token: str) -> str:
    """Crude plural folding so 'refunds' matches 'refund'.

    Not linguistics — just enough that a customer's phrasing does not decide
    whether they get an answer.
    """
    if len(token) > 3 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("es") and not token.endswith("ses"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def normalise(text: str) -> set[str]:
    return {_singularise(t) for t in tokenize(text)}


def expand(tokens: set[str]) -> set[str]:
    """Add domain synonyms to a query's terms."""
    out = set(tokens)
    for t in tokens:
        out |= _EXPANSIONS.get(t, set())
    return out


def _idf(corpus: list[set[str]]) -> Callable[[str], float]:
    total = len(corpus) or 1

    def weight(term: str) -> float:
        df = sum(1 for doc in corpus if term in doc)
        # A term in every document approaches zero weight; an unseen term gets
        # the maximum, so failing to match something rare is heavily penalised.
        return math.log((total + 1) / (df + 1)) + 1.0

    return weight


# A term matched in a record's title counts for more than one matched in its prose.
# In a corpus this small, IDF alone cannot separate "dispatch" (the subject of a
# policy) from "take" (an incidental word in another one) — they are equally rare,
# so the two tie and list order decides the answer. Where a term matched is the
# signal that breaks that tie honestly.
TITLE_BOOST = 2.0


def rank(
    query: str,
    items: Iterable[T],
    text_of: Callable[[T], Sequence[str]],
    limit: int = 3,
    min_relevance: float = MIN_RELEVANCE,
) -> list[T]:
    """Best matches first; anything below `min_relevance` is dropped entirely.

    `text_of` returns a record's searchable fields with its **title first** — the
    policy topic, the product name. That first field is weighted by `TITLE_BOOST`.

    Returning an empty list is a valid and important answer — it is what lets the
    agent say "I don't have that" instead of citing whatever was least unrelated.
    """
    candidates = list(items)
    if not candidates:
        return []

    fields = [[f for f in text_of(c)] for c in candidates]
    titles = [normalise(f[0]) if f else set() for f in fields]
    corpus = [normalise(" ".join(f for f in fs if f)) for fs in fields]
    weight = _idf(corpus)

    terms = expand(normalise(query))
    if not terms:
        return []

    total_weight = sum(weight(t) for t in terms)
    if total_weight <= 0:
        return []

    scored: list[tuple[float, int, T]] = []
    for index, item in enumerate(candidates):
        matched = terms & corpus[index]
        if not matched:
            continue
        earned = sum(
            weight(t) * (TITLE_BOOST if t in titles[index] else 1.0) for t in matched
        )
        # Capped so a title-boosted match stays comparable to a perfect one.
        relevance = min(earned / total_weight, 1.0)
        if relevance >= min_relevance:
            # `-index` keeps ordering deterministic when scores tie.
            scored.append((relevance, -index, item))

    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [item for _, _, item in scored[:limit]]
