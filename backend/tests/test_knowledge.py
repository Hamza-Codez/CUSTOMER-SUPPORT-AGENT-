"""Knowledge pipeline: parsing, embeddings, and hybrid retrieval.

The property under test throughout is the same one Phase 2 established and
Phase 3 depends on: retrieval that cannot miss is worse than no retrieval,
because it launders a guess into a citation.
"""

from __future__ import annotations

import pytest

from app.rag import keyword
from app.rag.embeddings import MockEmbedder, cosine, get_embedder, l2_normalise
from app.rag.ingest import ingest_knowledge_base
from app.rag.parser import KNOWLEDGE_DIR, parse_directory, parse_markdown, slugify
from app.rag.retriever import retrieve_policies

SAMPLE = """# Refund Policy

Some preamble that states no policy at all.

## Refund window {#refund-window}

Refunds are available within 30 days of delivery.

## A section without an anchor

Body text here.
"""


class TestParser:
    def test_sections_become_passages(self):
        passages = parse_markdown(SAMPLE, "refund-policy.md")
        assert len(passages) == 2
        assert passages[0].topic == "Refund window"
        assert "within 30 days" in passages[0].text

    def test_an_explicit_anchor_sets_the_source_ref(self):
        """Refs are authored so rewording a heading cannot break existing citations."""
        passages = parse_markdown(SAMPLE, "refund-policy.md")
        assert passages[0].source_ref == "refund-policy.md#refund-window"

    def test_a_missing_anchor_falls_back_to_a_slug(self):
        passages = parse_markdown(SAMPLE, "refund-policy.md")
        assert passages[1].source_ref == "refund-policy.md#a-section-without-an-anchor"

    def test_preamble_before_the_first_heading_is_dropped(self):
        """It describes the document rather than stating policy — citing it would
        point a customer at nothing they can act on."""
        text = " ".join(p.text for p in parse_markdown(SAMPLE, "d.md"))
        assert "preamble" not in text

    def test_the_anchor_is_stripped_from_the_topic(self):
        assert parse_markdown(SAMPLE, "d.md")[0].topic == "Refund window"

    def test_slugify(self):
        assert slugify("Order processing and dispatch") == "order-processing-and-dispatch"

    def test_the_real_documents_parse(self):
        passages = parse_directory()
        assert len(passages) >= 8
        refs = {p.source_ref for p in passages}
        # These refs appear in audit logs and agent answers; they are a contract.
        assert "refund-policy.md#refund-window" in refs
        assert "shipping-policy.md#dispatch" in refs
        assert "shipping-policy.md#delivery-areas" in refs
        assert "warranty-policy.md#cover" in refs

    def test_every_passage_is_citable_and_non_empty(self):
        for p in parse_directory():
            assert p.source_ref.count("#") == 1
            assert p.text.strip()
            assert p.doc.endswith(".md")

    def test_documents_exist_on_disk(self):
        """The knowledge base is files the seller could edit, not a Python literal."""
        assert sorted(f.name for f in KNOWLEDGE_DIR.glob("*.md"))


class TestEmbeddings:
    async def test_vectors_are_normalised(self):
        """Gemini returns unnormalised vectors below its native dimension, so
        similarity would otherwise depend on magnitude as well as direction."""
        vectors = await MockEmbedder(dim=64).embed(["refund policy", "delivery times"])
        for v in vectors:
            assert abs(sum(x * x for x in v) ** 0.5 - 1.0) < 1e-9

    def test_l2_normalise_handles_a_zero_vector(self):
        assert l2_normalise([0.0, 0.0]) == [0.0, 0.0]

    async def test_the_mock_embedder_is_deterministic(self):
        a = await MockEmbedder(dim=64).embed(["refund policy"])
        b = await MockEmbedder(dim=64).embed(["refund policy"])
        assert a == b

    async def test_similar_text_scores_above_unrelated_text(self):
        e = MockEmbedder(dim=512)
        q, related, unrelated = await e.embed(
            [
                "how do I get a refund",
                "Refunds are available within 30 days of delivery.",
                "Desks are delivered by a two-person carrier team.",
            ]
        )
        assert cosine(q, related) > cosine(q, unrelated)

    async def test_the_configured_dimension_is_respected(self, store):
        assert len(await get_embedder().embed(["x"])) == 1
        assert len((await get_embedder().embed(["x"]))[0]) == get_embedder().dim


class TestHybridRetrieval:
    """Keyword decides what is rejected; vectors only ever add.

    The two floors are asymmetric on purpose. Measured against this corpus with
    gemini-embedding-001, on-topic questions scored 0.607-0.780 and off-domain
    ones 0.381-0.582 — the ranges separate by 0.025, too little to place a
    rejection threshold between them.
    """

    @pytest.mark.parametrize(
        "question,expected",
        [
            ("how long does dispatch take?", "shipping-policy.md#dispatch"),
            ("can I get my money back after 60 days?", "refund-policy.md#refund-window"),
            ("what is your warranty cover?", "warranty-policy.md#cover"),
            ("my item arrived broken", "refund-policy.md#damaged-goods"),
            ("how do I start a return?", "returns-policy.md#starting-a-return"),
            ("when will it be delivered?", "shipping-policy.md#delivery-times"),
            ("do you ship to Mars?", "shipping-policy.md#delivery-areas"),
            ("can you post it overseas?", "shipping-policy.md#delivery-areas"),
            # Verbose phrasing: the extra unmatched words ("policy",
            # "interstellar") change the IDF denominator enough that the raw
            # keyword ranker prefers a passage merely containing the word
            # "shipping". Combining signals is what settles it correctly.
            (
                "what is your policy on interstellar shipping to Mars?",
                "shipping-policy.md#delivery-areas",
            ),
        ],
    )
    async def test_finds_the_right_passage(self, store, question, expected):
        hits = await retrieve_policies(store, "biz_demo", question, limit=2)
        assert hits, f"{question!r} returned nothing"
        assert hits[0].record.source_ref == expected

    @pytest.mark.parametrize(
        "question",
        [
            "do you accept cryptocurrency?",
            "what is the capital of France?",
            "can I pay in instalments?",
            "do you offer gift wrapping?",
            "who won the world cup in 1998?",
            "write me a poem about desks",
        ],
    )
    async def test_a_question_the_documents_do_not_answer_returns_nothing(
        self, store, question
    ):
        assert await retrieve_policies(store, "biz_demo", question, limit=2) == []

    async def test_every_hit_reports_which_signal_admitted_it(self, store):
        """Recorded in the audit log, so a bad answer can be traced to keyword or
        vector retrieval rather than guessed at."""
        hits = await retrieve_policies(store, "biz_demo", "warranty cover", limit=2)
        assert all(h.admitted_by in {"keyword", "vector"} for h in hits)

    async def test_retrieval_survives_an_embedding_failure(self, store, monkeypatch):
        """Keyword alone is a narrower net, never a wrong one."""

        async def boom(_text):
            raise RuntimeError("embedding provider down")

        monkeypatch.setattr("app.rag.retriever.embed_one", boom)
        hits = await retrieve_policies(store, "biz_demo", "warranty cover", limit=2)
        assert hits
        assert hits[0].record.source_ref == "warranty-policy.md#cover"

    async def test_another_tenants_passages_never_surface(self, store):
        hits = await retrieve_policies(store, "biz_demo", "unrelated seller", limit=5)
        assert all(h.record.source_ref != "other-tenant.md#fixture" for h in hits)

    async def test_an_empty_corpus_is_not_an_error(self, store):
        assert await retrieve_policies(store, "biz_nonexistent", "anything") == []

    async def test_the_keyword_floor_still_governs_rejection(self):
        """If this drifts, the miss property goes with it."""
        assert keyword.MIN_RELEVANCE == 0.30


class TestIngestion:
    async def test_ingest_loads_every_document(self, store):
        report = await ingest_knowledge_base(store, "biz_demo")
        assert report.passages >= 8
        assert report.embedded
        refs = {p.source_ref for p in await store.list_policies("biz_demo")}
        assert set(report.source_refs) <= refs

    async def test_ingest_is_idempotent(self, store):
        first = await ingest_knowledge_base(store, "biz_demo")
        before = len(await store.list_policies("biz_demo"))
        second = await ingest_knowledge_base(store, "biz_demo")
        after = len(await store.list_policies("biz_demo"))
        assert first.source_refs == second.source_refs
        assert before == after

    async def test_ingesting_one_tenant_leaves_another_alone(self, store):
        await ingest_knowledge_base(store, "biz_other")
        demo = {p.source_ref for p in await store.list_policies("biz_demo")}
        assert "other-tenant.md#fixture" not in demo
