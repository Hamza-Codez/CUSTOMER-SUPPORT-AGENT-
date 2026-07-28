"""Tool tests for product_catalog and policy_retriever.

Same frontier properties as order_lookup: tenancy scoping, typed misses, audit
coverage, and a model-facing payload that is JSON rather than Python repr.
"""

from __future__ import annotations

import json

from app.tools.policies import policy_retriever
from app.tools.products import product_catalog
from tests.conftest import invoke


class TestProductCatalog:
    async def test_finds_a_product(self, tenant):
        result = await invoke(product_catalog, tenant, query="lumbar cushion")
        assert result.outcome == "found"
        assert result.products[0].product_id == "PRD-CUSH-1"
        assert result.products[0].price == "29.50"
        assert result.products[0].in_stock is True

    async def test_reports_out_of_stock_truthfully(self, tenant):
        result = await invoke(product_catalog, tenant, query="cable tray")
        assert result.products[0].product_id == "PRD-TRAY-1"
        assert result.products[0].in_stock is False

    async def test_comparison_returns_multiple(self, tenant):
        result = await invoke(
            product_catalog, tenant, query="compare AeroDesk Pro and AeroDesk Lite"
        )
        ids = {p.product_id for p in result.products}
        assert {"PRD-DESK-1", "PRD-DESK-2"} <= ids

    async def test_no_match_is_typed_and_says_not_to_improvise(self, tenant):
        result = await invoke(product_catalog, tenant, query="scuba diving gear")
        assert result.outcome == "no_match"
        assert result.products == []
        assert "do not describe" in result.message.lower()

    async def test_never_returns_another_tenants_catalogue(self, tenant, other_tenant):
        mine = await invoke(product_catalog, tenant, query="widget")
        assert all(p.product_id != "PRD-OTHER-1" for p in mine.products)

        theirs = await invoke(product_catalog, other_tenant, query="widget")
        assert theirs.outcome == "found"
        assert theirs.products[0].product_id == "PRD-OTHER-1"

    async def test_reads_are_audited(self, tenant, store):
        await invoke(product_catalog, tenant, query="lumbar cushion")
        entry = (await store.recent_audit("biz_demo"))[0]
        assert entry.action == "product_catalog"
        assert entry.outcome == "found"

    async def test_misses_are_audited_too(self, tenant, store):
        await invoke(product_catalog, tenant, query="scuba diving gear")
        assert (await store.recent_audit("biz_demo"))[0].outcome == "no_match"

    async def test_model_sees_json(self, tenant):
        result = await invoke(product_catalog, tenant, query="lumbar cushion")
        payload = json.loads(str(result))
        assert payload["products"][0]["name"] == "AeroChair Lumbar Cushion"


class TestPolicyRetriever:
    async def test_returns_a_passage_with_a_source(self, tenant):
        result = await invoke(policy_retriever, tenant, question="how long does dispatch take?")
        assert result.outcome == "found"
        assert result.passages[0].topic == "Order processing and dispatch"
        assert result.passages[0].source_ref == "shipping-policy.md#dispatch"

    async def test_every_passage_carries_a_source_ref(self, tenant):
        result = await invoke(policy_retriever, tenant, question="refund policy")
        assert result.passages
        assert all(p.source_ref for p in result.passages)

    async def test_an_off_domain_question_returns_no_passages(self, tenant):
        """The grounding property: no passage means no answer, not a plausible one."""
        result = await invoke(
            policy_retriever, tenant, question="do you accept cryptocurrency?"
        )
        assert result.outcome == "no_match"
        assert result.passages == []
        assert "do not answer from your own knowledge" in result.message.lower()

    async def test_an_on_topic_question_returns_the_topical_passage(self, tenant):
        """Retrieval answers by *topic*, and that is the correct behaviour.

        "Do you ship to Mars" returns the delivery-areas passage, which states we
        do not ship outside our listed regions — a real answer, from a real
        document. What must never happen is the earlier defect: a shipping
        question coming back holding the damaged-goods policy, which invites a
        confident answer on entirely the wrong subject.
        """
        result = await invoke(
            policy_retriever, tenant, question="do you ship to Mars?"
        )
        assert result.outcome == "found"
        assert result.passages[0].source_ref == "shipping-policy.md#delivery-areas"

    async def test_never_returns_another_tenants_policy(self, tenant):
        result = await invoke(policy_retriever, tenant, question="unrelated seller policy")
        for p in result.passages:
            assert p.source_ref != "other-tenant.md#fixture"

    async def test_reads_are_audited_with_their_sources(self, tenant, store):
        await invoke(policy_retriever, tenant, question="warranty cover")
        entry = (await store.recent_audit("biz_demo"))[0]
        assert entry.action == "policy_retriever"
        assert entry.outcome == "found"
        assert "warranty-policy.md#cover" in entry.detail["sources"]

    async def test_model_sees_json(self, tenant):
        result = await invoke(policy_retriever, tenant, question="warranty cover")
        payload = json.loads(str(result))
        assert payload["passages"][0]["source_ref"] == "warranty-policy.md#cover"


class TestToolSchemas:
    def test_tenancy_is_never_a_model_facing_parameter(self):
        """The model must not be able to name the tenant it reads from."""
        for tool, expected in [
            (product_catalog, {"query"}),
            (policy_retriever, {"question"}),
        ]:
            props = set(tool.params_json_schema["properties"])
            assert props == expected
            assert "business_id" not in json.dumps(tool.params_json_schema)
