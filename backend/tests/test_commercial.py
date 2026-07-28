"""Integration requests and the analytics signals.

The analytics rules that matter are about *absence*: a rate with nothing behind
it is null, not zero, and a cost nobody has priced is unavailable rather than
free. A dashboard that cannot tell those apart will be believed at exactly the
wrong moment.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

CUST = {"Authorization": "Bearer demo-token"}
OPS = {"Authorization": "Bearer ops-token"}
OTHER = {"Authorization": "Bearer other-token"}

FORM = {
    "contact_name": "Ayesha K.",
    "contact_email": "ayesha@aeron.example.com",
    "website": "https://aeron.example.com",
    "platform": "Shopify",
    "monthly_conversations": "2000",
    "notes": "We want it on the product pages too.",
}


@pytest.fixture
def client(store):
    with TestClient(app) as c:
        yield c


class TestIntegrationRequests:
    def test_a_seller_can_ask_to_embed(self, client):
        r = client.post("/integrations/request", json=FORM, headers=CUST)
        assert r.status_code == 201
        body = r.json()
        assert body["request_id"].startswith("int_")
        assert body["status"] == "received"

    def test_it_becomes_a_record_not_a_dead_end(self, client):
        client.post("/integrations/request", json=FORM, headers=CUST)
        listed = client.get("/dashboard/integrations", headers=OPS).json()["requests"]
        assert len(listed) == 1
        assert listed[0]["contact_email"] == "ayesha@aeron.example.com"
        assert listed[0]["platform"] == "Shopify"
        assert listed[0]["status"] == "new"

    def test_it_is_audited(self, client, store):
        async def check():
            entries = await store.recent_audit("biz_demo")
            assert any(e.action == "integration_request" for e in entries)

        client.post("/integrations/request", json=FORM, headers=CUST)
        import asyncio

        asyncio.run(check())

    def test_it_needs_a_token(self, client):
        assert client.post("/integrations/request", json=FORM).status_code == 401

    def test_the_form_is_validated(self, client):
        assert (
            client.post(
                "/integrations/request",
                json={"contact_name": "", "contact_email": "a@b.c"},
                headers=CUST,
            ).status_code
            == 422
        )

    def test_only_an_operator_can_read_the_list(self, client):
        assert client.get("/dashboard/integrations", headers=CUST).status_code == 403

    def test_requests_are_tenant_scoped(self, client):
        client.post("/integrations/request", json=FORM, headers=OTHER)
        listed = client.get("/dashboard/integrations", headers=OPS).json()["requests"]
        assert listed == []


class TestAnalytics:
    def test_only_an_operator_can_read_it(self, client):
        assert client.get("/dashboard/analytics", headers=CUST).status_code == 403
        assert client.get("/dashboard/analytics", headers=OPS).status_code == 200

    def test_rates_are_null_not_zero_before_any_data(self, client):
        """A deflection rate of 100% from zero conversations is not a good
        number, it is an absent one."""
        body = client.get("/dashboard/analytics", headers=OPS).json()
        assert body["conversations"] == 0
        assert body["deflection_rate"] is None
        assert body["handoff_approval_rate"] is None
        assert body["csat_average"] is None
        assert body["tokens_per_conversation"] is None

    def test_conversations_are_counted_once_each(self, client):
        for message in ["hello", "how long does dispatch take?"]:
            client.post(
                "/chat",
                json={"message": message, "session_id": "one"},
                headers=CUST,
            )
        body = client.get("/dashboard/analytics", headers=OPS).json()
        assert body["conversations"] == 1

    def test_a_fully_handled_conversation_counts_as_deflected(self, client):
        client.post(
            "/chat",
            json={"message": "how long does dispatch take?", "session_id": "d1"},
            headers=CUST,
        )
        body = client.get("/dashboard/analytics", headers=OPS).json()
        assert body["escalated_conversations"] == 0
        assert body["deflection_rate"] == 1.0

    def test_an_escalated_conversation_lowers_deflection(self, client):
        client.post(
            "/chat",
            json={"message": "how long does dispatch take?", "session_id": "d1"},
            headers=CUST,
        )
        client.post(
            "/chat",
            json={
                "message": "refund ORD-1001, email ayesha.k@example.com",
                "session_id": "d2",
            },
            headers=CUST,
        )
        body = client.get("/dashboard/analytics", headers=OPS).json()
        assert body["conversations"] == 2
        assert body["escalated_conversations"] == 1
        assert body["deflection_rate"] == 0.5

    def test_approval_rate_counts_only_settled_cards(self, client):
        client.post(
            "/chat",
            json={
                "message": "refund ORD-1001, email ayesha.k@example.com",
                "session_id": "a1",
            },
            headers=CUST,
        )
        # Pending only — nothing settled, so there is no rate to report yet.
        assert (
            client.get("/dashboard/analytics", headers=OPS).json()[
                "handoff_approval_rate"
            ]
            is None
        )

        card = client.get("/dashboard/escalations", headers=OPS).json()["escalations"][0]
        client.post(
            f"/escalations/{card['escalation_id']}/decision",
            json={"decision": "approve"},
            headers=OPS,
        )
        body = client.get("/dashboard/analytics", headers=OPS).json()
        assert body["handoff_approval_rate"] == 1.0
        assert body["escalations"]["approved"] == 1
        assert body["refunds_executed"] >= 1

    def test_csat_comes_from_real_ratings(self, client, store):
        import asyncio

        for message in [
            "where is ORD-1002? email ayesha.k@example.com",
            "email me a summary",
        ]:
            client.post(
                "/chat", json={"message": message, "session_id": "c1"}, headers=CUST
            )
        email = asyncio.run(store.get_email_for_session("biz_demo", "c1"))
        client.get(f"/feedback/{email.feedback_token}?rating=4")

        body = client.get("/dashboard/analytics", headers=OPS).json()
        assert body["csat_responses"] == 1
        assert body["csat_average"] == 4.0


class TestCostReporting:
    def test_cost_is_unavailable_when_no_price_is_configured(self, client):
        body = client.get("/dashboard/analytics", headers=OPS).json()
        assert body["cost_per_conversation"] is None
        assert "COST_PER_MTOK_INPUT" in body["cost_note"]

    def test_cost_is_not_reported_as_zero_on_the_mock_provider(
        self, client, monkeypatch
    ):
        """The mock provider consumes no tokens. Presenting that as a cost of
        zero would be a claim about a real price."""
        monkeypatch.setenv("COST_PER_MTOK_INPUT", "0.30")
        monkeypatch.setenv("COST_PER_MTOK_OUTPUT", "2.50")
        get_settings.cache_clear()

        client.post(
            "/chat", json={"message": "hello", "session_id": "cost"}, headers=CUST
        )
        body = client.get("/dashboard/analytics", headers=OPS).json()

        assert body["total_tokens"] == 0
        assert body["cost_per_conversation"] is None
        assert "mock provider" in body["cost_note"]
        get_settings.cache_clear()

    async def test_usage_is_recorded_per_turn(self, client, store):
        client.post(
            "/chat", json={"message": "hello", "session_id": "u1"}, headers=CUST
        )
        summary = await store.usage_summary("biz_demo")
        assert summary.conversations == 1
        assert summary.model_requests >= 0
        assert "mock" in summary.providers

    async def test_usage_is_tenant_scoped(self, client, store):
        client.post(
            "/chat", json={"message": "hello", "session_id": "u2"}, headers=CUST
        )
        assert (await store.usage_summary("biz_other")).conversations == 0
