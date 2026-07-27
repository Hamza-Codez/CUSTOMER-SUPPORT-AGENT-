"""Retrieval tests.

The miss cases matter more than the hit cases. Retrieval that always returns
something cannot miss, so the agent never learns it doesn't know — it just cites
whatever was least unrelated. Each `None` expectation below is a guard against
that.

These also pin the two defects found by smoke-testing Phase 2: a question about
interstellar shipping came back holding the damaged-goods policy, and "money back
after 60 days" matched the dispatch policy because both mention "after" and "day".
"""

from __future__ import annotations

import pytest

from app.rag import keyword

POLICY_TEXT = lambda p: (p.topic, p.text)  # noqa: E731
PRODUCT_TEXT = lambda p: (  # noqa: E731
    p.name,
    p.summary,
    " ".join(p.attributes.values()),
)


@pytest.fixture
async def policies(store):
    return await store.list_policies("biz_demo")


@pytest.fixture
async def products(store):
    return await store.list_products("biz_demo")


class TestPolicyRetrieval:
    @pytest.mark.parametrize(
        "question,expected_topic",
        [
            ("how long does dispatch take?", "Order processing and dispatch"),
            ("can I get my money back after 60 days?", "Refund window"),
            ("what is your warranty cover?", "Warranty cover"),
            ("my item arrived broken", "Damaged or faulty goods"),
            ("how do I start a return?", "How to start a return"),
            ("when will it be delivered?", "Delivery times and methods"),
            # Customer vocabulary that does not appear in the policy text at all.
            ("I want my money back", "Refund window"),
            ("my order turned up damaged", "Damaged or faulty goods"),
        ],
    )
    async def test_finds_the_right_passage(self, policies, question, expected_topic):
        got = keyword.rank(question, policies, text_of=POLICY_TEXT, limit=2)
        assert got, f"{question!r} returned nothing"
        assert got[0].topic == expected_topic

    @pytest.mark.parametrize(
        "question",
        [
            "do you accept cryptocurrency?",
            "what is the capital of France?",
            "can I pay in instalments?",
            "do you offer gift wrapping?",
            "who won the world cup in 1998?",
        ],
    )
    async def test_returns_nothing_rather_than_something_irrelevant(
        self, policies, question
    ):
        """A miss must be empty. Anything else licenses a confident wrong answer."""
        assert keyword.rank(question, policies, text_of=POLICY_TEXT, limit=2) == []

    async def test_a_shipping_destination_question_surfaces_the_delivery_areas_passage(
        self, policies
    ):
        """Once the documents cover a question, the honest answer is the passage.

        This was previously a miss case: shipping to Mars had no answer in the
        corpus, so returning nothing was correct. The shipping policy now has a
        "Where we deliver" section, so the right behaviour changed with the
        documents rather than with the code.

        Asserted as membership, not as the top hit: which of two shipping-related
        passages ranks first is settled by the hybrid retriever combining signals,
        and that ordering is tested against `retrieve_policies` in
        tests/test_knowledge.py. This layer only owns whether the passage is found
        at all.
        """
        got = keyword.rank(
            "what is your policy on interstellar shipping to Mars?",
            policies,
            text_of=POLICY_TEXT,
            limit=3,
        )
        assert "shipping-policy.md#delivery-areas" in {p.source_ref for p in got}

    async def test_every_returned_passage_can_be_cited(self, policies):
        for p in policies:
            assert p.source_ref, f"{p.topic} has no source_ref"


class TestProductRetrieval:
    @pytest.mark.parametrize(
        "query,expected_name",
        [
            ("do you sell a lumbar cushion?", "AeroChair Lumbar Cushion"),
            ("I need an ergonomic chair", "AeroChair Ergonomic Task Chair"),
            ("cable tray", "AeroDesk Cable Tray"),
        ],
    )
    async def test_finds_the_right_product(self, products, query, expected_name):
        got = keyword.rank(query, products, text_of=PRODUCT_TEXT, limit=3)
        assert got
        assert got[0].name == expected_name

    async def test_comparison_returns_both_desks(self, products):
        got = keyword.rank(
            "compare the AeroDesk Pro and the AeroDesk Lite",
            products,
            text_of=PRODUCT_TEXT,
            limit=3,
        )
        names = [p.name for p in got]
        assert "AeroDesk Pro Standing Desk" in names
        assert "AeroDesk Lite Standing Desk" in names

    async def test_unstocked_range_returns_nothing(self, products):
        assert keyword.rank(
            "do you sell scuba diving equipment?",
            products,
            text_of=PRODUCT_TEXT,
            limit=3,
        ) == []


class TestRankingMechanics:
    def test_a_title_match_outranks_a_body_match(self):
        """The fix for 'dispatch': equally rare terms tied, so list order decided."""

        class Doc:
            def __init__(self, title, body):
                self.title, self.body = title, body

        docs = [
            Doc("Refund window", "Refunds take 5-10 business days to appear."),
            Doc("Order processing and dispatch", "Orders are dispatched same day."),
        ]
        got = keyword.rank(
            "how long does dispatch take?",
            docs,
            text_of=lambda d: (d.title, d.body),
            limit=2,
        )
        assert got[0].title == "Order processing and dispatch"

    def test_empty_corpus_is_not_an_error(self):
        assert keyword.rank("anything", [], text_of=lambda x: (x,)) == []

    def test_query_of_only_stopwords_returns_nothing(self, ):
        class Doc:
            title = "Refund window"
            body = "Refunds within 30 days."

        assert keyword.rank(
            "what about the", [Doc()], text_of=lambda d: (d.title, d.body)
        ) == []

    def test_stopwords_and_plurals(self):
        assert "the" not in keyword.tokenize("the refund")
        assert keyword.normalise("refunds") == {"refund"}
        assert keyword.normalise("policies") == {"policy"}

    def test_domain_synonyms_bridge_customer_wording(self):
        assert "refund" in keyword.expand(keyword.normalise("money"))
        assert "delivery" in keyword.expand(keyword.normalise("shipping"))
        assert "damaged" in keyword.expand(keyword.normalise("broken"))
