"""Embedding provider switch — the second axis of `model.py`, for retrieval.

    EMBEDDING_PROVIDER = mock | openai | ollama     (default: mock)
    EMBEDDING_DIM      = 1536                        (must match kb_docs.vector(n))

The mock embedder is a hashed bag-of-words projection: deterministic, offline,
and — unlike random vectors — genuinely lexically meaningful, so cosine
similarity over pgvector behaves like keyword overlap. That keeps the whole
vector path demoable and testable with no API key, per INTENT §5.

It is NOT semantic: 'refund' and 'money back' are orthogonal to it. Switch to
`openai` for real semantic retrieval; the dimension and schema are unchanged.
"""
from __future__ import annotations

import hashlib
import math
import os
import re

DEFAULT_DIM = 1536

# A hashed bag-of-words is dominated by function words — without this filter,
# "is it a the" scores higher than a real question. Real embedding models handle
# this themselves; the filter applies to the mock embedder only.
_STOPWORDS = {
    "the", "and", "for", "are", "you", "your", "our", "can", "does", "did", "was",
    "were", "with", "what", "when", "where", "why", "how", "this", "that", "there",
    "here", "please", "need", "want", "have", "has", "had", "will", "would", "about",
    "from", "get", "got", "any", "all", "not", "but", "its", "his", "her", "them",
    "they", "she", "hers", "him", "who", "whom", "been", "being", "into", "than",
    "then", "some", "much", "many", "just", "know", "tell", "let",
}


def embedding_dim() -> int:
    return int(os.getenv("EMBEDDING_DIM", DEFAULT_DIM))


def provider_name() -> str:
    return os.getenv("EMBEDDING_PROVIDER", "mock").lower()


def _mock_embed(text: str, dim: int) -> list[float]:
    """Hash each token into a bucket, then L2-normalise so cosine == overlap."""
    vec = [0.0] * dim
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if len(token) < 3 or token in _STOPWORDS:
            continue
        digest = hashlib.sha1(token.encode()).digest()
        bucket = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 else -1.0
        vec[bucket] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm:
        vec = [v / norm for v in vec]
    return vec


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch. Same call shape for every provider."""
    provider = provider_name()
    dim = embedding_dim()

    if provider == "mock":
        return [_mock_embed(t, dim) for t in texts]

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        model = OpenAIEmbeddings(model=os.getenv("OPENAI_EMBEDDING_MODEL",
                                                 "text-embedding-3-small"))
        return model.embed_documents(texts)

    if provider == "ollama":
        # nomic-embed-text is 768-dim — set EMBEDDING_DIM=768 and migrate the
        # kb_docs column to match, or the insert will be rejected.
        from langchain_ollama import OllamaEmbeddings
        model = OllamaEmbeddings(
            model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        return model.embed_documents(texts)

    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER '{provider}' (use mock | openai | ollama)"
    )


def embed_query(text: str) -> list[float]:
    return embed([text])[0]
