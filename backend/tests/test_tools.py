"""Tool-layer tests — the data frontier.

These cover the properties the whole security story rests on: tenancy scoping,
identity verification, PII containment and audit coverage.
"""

from __future__ import annotations

import pytest

from app.schemas import OrderLookupResult
from app.tools.orders import normalise_order_id, order_lookup
from tests.conftest import invoke


class TestOrderLookup:
    async def test_found_returns_scoped_status(self, tenant):
        result: OrderLookupResult = await invoke(
            order_lookup, tenant, order_id="ORD-1002", email="ayesha.k@example.com"
        )
        assert result.outcome == "found"
        assert result.order is not None
        assert result.order.order_id == "ORD-1002"
        assert result.order.status == "in_transit"
        assert result.order.carrier == "FedEx"
        assert result.order.item_count == 2
        assert result.order.total == "59.00"

    async def test_unknown_order_is_a_typed_result_not_an_exception(self, tenant):
        result = await invoke(
            order_lookup, tenant, order_id="ORD-9999", email="ayesha.k@example.com"
        )
        assert result.outcome == "not_found"
        assert result.order is None

    async def test_wrong_email_withholds_the_order(self, tenant):
        result = await invoke(
            order_lookup, tenant, order_id="ORD-1002", email="attacker@example.com"
        )
        assert result.outcome == "identity_mismatch"
        # The order exists, but nothing about it may leak on a failed identity check.
        assert result.order is None
        assert "in_transit" not in str(result)
        assert "FedEx" not in str(result)

    async def test_email_match_is_case_insensitive(self, tenant):
        result = await invoke(
            order_lookup, tenant, order_id="ORD-1002", email="Ayesha.K@Example.COM"
        )
        assert result.outcome == "found"

    @pytest.mark.parametrize(
        "typed", ["ORD-1002", "ord-1002", "ord 1002", "ORD1002", "  ord-1002  "]
    )
    async def test_order_id_is_normalised(self, tenant, typed):
        result = await invoke(
            order_lookup, tenant, order_id=typed, email="ayesha.k@example.com"
        )
        assert result.outcome == "found"

    async def test_customer_pii_never_reaches_the_model(self, tenant):
        """The model-facing string must not contain the customer's identity."""
        result = await invoke(
            order_lookup, tenant, order_id="ORD-1002", email="ayesha.k@example.com"
        )
        model_sees = str(result)
        assert "ayesha.k@example.com" not in model_sees
        assert "Ayesha" not in model_sees

    async def test_result_serialises_as_json_for_the_model(self, tenant):
        """Guards the __str__ override: the SDK would otherwise send Python repr."""
        import json

        result = await invoke(
            order_lookup, tenant, order_id="ORD-1002", email="ayesha.k@example.com"
        )
        payload = json.loads(str(result))
        assert payload["outcome"] == "found"
        assert payload["order"]["order_id"] == "ORD-1002"


class TestTenancy:
    async def test_business_id_is_not_a_model_facing_parameter(self):
        """The model must not be able to name the tenant it reads from."""
        schema = order_lookup.params_json_schema
        assert set(schema["properties"]) == {"order_id", "email"}
        assert "business_id" not in json_dumps(schema)

    async def test_same_order_id_resolves_per_tenant(self, tenant, other_tenant):
        """ORD-1002 exists for both businesses and must never cross over."""
        mine = await invoke(
            order_lookup, tenant, order_id="ORD-1002", email="ayesha.k@example.com"
        )
        theirs = await invoke(
            order_lookup,
            other_tenant,
            order_id="ORD-1002",
            email="someone@other.example.com",
        )
        assert mine.order.status == "in_transit"
        assert theirs.order.status == "cancelled"

    async def test_cannot_read_another_tenants_order_with_their_email(self, tenant):
        """Correct credentials for the *other* tenant still fail under this tenant."""
        result = await invoke(
            order_lookup,
            tenant,
            order_id="ORD-1002",
            email="someone@other.example.com",
        )
        assert result.outcome == "identity_mismatch"


class TestAudit:
    async def test_successful_read_is_logged(self, tenant, store):
        await invoke(
            order_lookup, tenant, order_id="ORD-1002", email="ayesha.k@example.com"
        )
        entry = (await store.recent_audit("biz_demo"))[0]
        assert entry.action == "order_lookup"
        assert entry.target == "ORD-1002"
        assert entry.outcome == "found"
        assert entry.actor == "customer:demo-token"

    async def test_refused_read_is_also_logged(self, tenant, store):
        """A denied identity check is exactly the event worth having on record."""
        await invoke(
            order_lookup, tenant, order_id="ORD-1002", email="attacker@example.com"
        )
        entry = (await store.recent_audit("biz_demo"))[0]
        assert entry.outcome == "identity_mismatch"
        assert entry.detail["supplied_email"] == "attacker@example.com"

    async def test_audit_is_tenant_scoped(self, tenant, other_tenant, store):
        await invoke(
            order_lookup, tenant, order_id="ORD-1002", email="ayesha.k@example.com"
        )
        assert await store.recent_audit("biz_other") == []


def json_dumps(obj) -> str:
    import json

    return json.dumps(obj)


def test_normalise_order_id_leaves_unrecognised_input_alone():
    assert normalise_order_id("not-an-order") == "NOT-AN-ORDER"
    assert normalise_order_id("") == ""
