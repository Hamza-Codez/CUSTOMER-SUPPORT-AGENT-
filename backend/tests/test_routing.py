"""Orchestrator routing and handoffs, end to end through /chat.

These assert our wiring — that a message reaches the right specialist, that the
specialist's tool runs, and that the handoff is visible to the UI. They do not
assert how a language model phrases anything, and they are not evidence that
Gemini routes identically; that is checked separately against the live model.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

AUTH = {"Authorization": "Bearer demo-token"}


@pytest.fixture
def client(store):
    with TestClient(app) as c:
        yield c


def send(client, message: str, session_id: str = "r1") -> dict:
    r = client.post(
        "/chat", json={"message": message, "session_id": session_id}, headers=AUTH
    )
    assert r.status_code == 200, r.text
    return r.json()


def kinds(body: dict) -> list[str]:
    return [a["kind"] for a in body["actions"]]


def routed_to(body: dict) -> str | None:
    for a in body["actions"]:
        if a["kind"] == "routed":
            return a["ref"]
    return None


class TestRouting:
    @pytest.mark.parametrize(
        "message,expected_agent",
        [
            ("where is my order ORD-1002?", "Orders"),
            ("track my delivery", "Orders"),
            ("I want a refund", "Refunds"),
            ("can I get my money back?", "Refunds"),
            ("compare the AeroDesk Pro and the AeroDesk Lite", "Products"),
            ("do you sell a lumbar cushion?", "Products"),
            ("how long does dispatch take?", "Support"),
            ("what is your warranty cover?", "Support"),
        ],
    )
    def test_message_reaches_the_right_specialist(
        self, client, message, expected_agent
    ):
        body = send(client, message, session_id=f"route-{expected_agent}-{len(message)}")
        assert routed_to(body) == expected_agent

    def test_an_unclassifiable_message_still_routes_somewhere(self, client):
        """Never a dead end: Support is the safe default."""
        body = send(client, "I have a question about something", session_id="vague")
        assert routed_to(body) is not None

    def test_the_handoff_is_visible_to_the_ui(self, client):
        body = send(client, "what is your warranty cover?", session_id="vis")
        assert body["actions"][0]["kind"] == "routed"
        assert body["actions"][0]["label"] == "Routed to Support"


class TestSpecialistsRunTheirTools:
    def test_orders_specialist_looks_the_order_up(self, client):
        body = send(
            client,
            "where is ORD-1002? email ayesha.k@example.com",
            session_id="s-orders",
        )
        assert kinds(body) == ["routed", "order_looked_up"]
        assert "ORD-1002" in body["reply"]

    def test_support_specialist_cites_a_source(self, client):
        body = send(client, "how long does dispatch take?", session_id="s-support")
        assert "policy_cited" in kinds(body)
        cited = next(a for a in body["actions"] if a["kind"] == "policy_cited")
        assert cited["ref"] == "shipping-policy.md#dispatch"
        assert cited["ref"] in body["reply"]

    def test_products_specialist_compares(self, client):
        body = send(
            client,
            "compare the AeroDesk Pro and the AeroDesk Lite",
            session_id="s-products",
        )
        assert "products_compared" in kinds(body)

    def test_refunds_specialist_reads_policy_before_ruling(self, client):
        body = send(client, "I want a refund for my order", session_id="s-refunds")
        assert routed_to(body) == "Refunds"
        assert "policy_cited" in kinds(body)

    def test_the_refund_tool_is_gated_wherever_it_appears(self, client):
        """`refund_processor` has never existed ungated, and must not start now."""
        from app.agents.orchestrator import get_entry_agent

        refunds = next(
            a for a in get_entry_agent().handoffs if getattr(a, "name", "") == "Refunds"
        )
        assert {t.name for t in refunds.tools} == {
            "policy_retriever",
            "order_lookup",
            "refund_processor",
            "human_escalation",
            "send_summary_email",
        }

        refund_tool = next(t for t in refunds.tools if t.name == "refund_processor")
        # A callable needs_approval means the decision is computed per call, not
        # a blanket True/False someone can flip.
        assert callable(refund_tool.needs_approval)
        assert refund_tool.tool_input_guardrails

    def test_no_other_agent_can_reach_the_refund_tool(self, client):
        """Least privilege is structural: Support literally cannot spend money."""
        from app.agents.orchestrator import get_entry_agent

        for agent in get_entry_agent().handoffs:
            if getattr(agent, "name", "") == "Refunds":
                continue
            assert "refund_processor" not in {t.name for t in agent.tools}


class TestGroundingBehaviour:
    def test_an_unanswerable_policy_question_is_refused_not_invented(self, client):
        # Genuinely absent from the documents. (Shipping destinations used to sit
        # here, until the shipping policy gained a "Where we deliver" section and
        # the honest answer became the passage rather than a refusal.)
        body = send(
            client,
            "do you accept cryptocurrency as payment?",
            session_id="crypto",
        )
        assert "no_policy_match" in kinds(body)
        assert "policy_cited" not in kinds(body)
        # It must not have quoted a real, unrelated policy at the customer.
        assert "dispatched the same day" not in body["reply"]
        assert "30 days" not in body["reply"]

    def test_an_uncatalogued_product_is_refused_not_invented(self, client):
        body = send(client, "do you sell scuba diving equipment?", session_id="scuba")
        assert "no_product_match" in kinds(body)
        assert "AeroDesk" not in body["reply"]


class TestTenancyThroughTheApi:
    def test_another_tenant_sees_only_their_own_catalogue(self, client):
        body = send(client, "do you sell a lumbar cushion?", session_id="t-mine")
        assert "AeroChair Lumbar Cushion" in body["reply"]

        r = client.post(
            "/chat",
            json={"message": "do you sell a lumbar cushion?", "session_id": "t-theirs"},
            headers={"Authorization": "Bearer other-token"},
        )
        assert "AeroChair" not in r.json()["reply"]
