"""Embedding providers — one factory, two implementations.

Both return **L2-normalised** vectors of the same dimension, so the database
column never changes when the provider does, and cosine similarity is a plain dot
product everywhere.

Normalisation is not decorative here: Gemini returns *unnormalised* vectors when
you request fewer than the native 3072 dimensions (measured L2 norms of 0.59 at
768 and 0.70 at 1536). Storing those raw would make similarity scores depend on
vector length as well as direction, and any threshold tuned against them would be
meaningless.
"""

from __future__ import annotations

import hashlib
import math
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.rag import keyword


def l2_normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]


def cosine(a: list[float], b: list[float]) -> float:
    """Dot product; correct because every vector here is already normalised."""
    return sum(x * y for x, y in zip(a, b))


class Embedder(Protocol):
    dim: int
    name: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class MockEmbedder:
    """Deterministic embeddings, no API key, no quota.

    A hashed bag of words: each token is hashed into a bucket and accumulated, so
    cosine similarity between two texts approximates their weighted lexical
    overlap. That makes the mock provider *meaningfully* similar rather than
    randomly similar — the same query that finds the refund policy on Gemini finds
    it here — while staying free and instant.

    It is genuinely lexical, not semantic: it shares the tokenizer, stopwords and
    domain synonyms with `keyword.py`, so "money back" reaches "refund", but
    nothing beyond the synonyms it is told about.
    """

    name = "mock"

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in keyword.expand(keyword.normalise(text)):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dim] += 1.0
        # Weights stay positive on purpose. An earlier version assigned each token
        # a pseudo-random sign, which let unrelated tokens cancel and made cosine
        # similarity close to noise — measured 4/9 top-1 accuracy, with off-domain
        # questions outscoring on-topic ones. Plain positive counts give cosine of
        # the token sets, which is a real (if shallow) lexical similarity.
        return l2_normalise(vector)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class GeminiEmbedder:
    """Gemini embeddings through the OpenAI-compatible endpoint.

    Uses a different quota bucket from chat completions, so retrieval keeps
    working on days when the chat model is exhausted.
    """

    name = "gemini"

    def __init__(self, api_key: str, base_url: str, model: str, dim: int) -> None:
        from openai import AsyncOpenAI

        self.dim = dim
        self._model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
            dimensions=self.dim,
        )
        # OpenAI returns an `index` on each item; Gemini's compatible endpoint
        # leaves it null, so sorting on it raises. Reorder when the field is
        # populated, and otherwise trust response order — which is what the
        # endpoint actually returns, and the only thing available.
        items = list(response.data)
        if all(getattr(d, "index", None) is not None for d in items):
            items.sort(key=lambda d: d.index)
        return [l2_normalise(list(d.embedding)) for d in items]


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()

    if settings.embedding_provider == "mock":
        return MockEmbedder(dim=settings.embedding_dim)

    if settings.embedding_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError(
                "EMBEDDING_PROVIDER=gemini but GEMINI_API_KEY is empty. "
                "Set it in backend/.env, or use EMBEDDING_PROVIDER=mock."
            )
        return GeminiEmbedder(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
            model=settings.embedding_model,
            dim=settings.embedding_dim,
        )

    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER {settings.embedding_provider!r}. "
        "Expected 'mock' or 'gemini'."
    )


async def embed_one(text: str) -> list[float]:
    return (await get_embedder().embed([text]))[0]
