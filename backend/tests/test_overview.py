"""The operator's own view of their store, and the summary email preview.

Both exist to serve the demo playground's later steps with real data rather than
a mock-up. Both are operator-only, and neither is reachable by a tool — nothing
here is exposed to the model.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

CUST = {"Authorization": "Bearer demo-token"}
OPS = {"Authorization": "Bearer ops-token"}
OTHER = {"Authorization": "Bearer other-token"}


@pytest.fixture
def client(store):
    with TestClient(app) as c:
        yield c


class TestOverview:
    def test_only_an_operator_may_read_it(self, client):
        assert client.get("/dashboard/overview", headers=CUST).status_code == 403
        assert client.get("/dashboard/overview").status_code == 401
        assert client.get("/dashboard/overview", headers=OPS).status_code == 200

    def test_it_reports_the_store(self, client):
        body = client.get("/dashboard/overview", headers=OPS).json()

        assert {o["order_id"] for o in body["orders"]} >= {
            "ORD-1001",
            "ORD-1002",
            "ORD-1005",
        }
        assert {p["product_id"] for p in body["products"]} >= {
            "PRD-DESK-1",
            "PRD-CUSH-1",
        }
        assert any(
            p["source_ref"] == "shipping-policy.md#dispatch" for p in body["policies"]
        )

    def test_stock_is_reported_truthfully(self, client):
        body = client.get("/dashboard/overview", headers=OPS).json()
        tray = next(p for p in body["products"] if p["product_id"] == "PRD-TRAY-1")
        assert tray["in_stock"] is False
        assert tray["stock"] == 0
        assert body["counts"]["out_of_stock"] >= 1

    def test_customer_email_is_not_included(self, client):
        """Operators own the relationship, but these screens have no use for it,
        so it stays out of the payload."""
        body = client.get("/dashboard/overview", headers=OPS).text
        assert "ayesha.k@example.com" not in body

    def test_activity_shows_what_the_agent_did(self, client):
        client.post(
            "/chat",
            json={
                "message": "where is ORD-1002? email ayesha.k@example.com",
                "session_id": "ov",
            },
            headers=CUST,
        )
        body = client.get("/dashboard/overview", headers=OPS).json()
        actions = [a["action"] for a in body["recent_activity"]]
        assert "order_lookup" in actions

    def test_it_is_tenant_scoped(self, client):
        """biz_other has its own single product and must not see biz_demo's."""
        body = client.get("/dashboard/overview", headers=OPS).json()
        assert all(p["product_id"] != "PRD-OTHER-1" for p in body["products"])


class TestEmailPreview:
    def _send_summary(self, client, session="prev"):
        client.post(
            "/chat",
            json={
                "message": "where is ORD-1002? email ayesha.k@example.com",
                "session_id": session,
            },
            headers=CUST,
        )
        client.post(
            "/chat",
            json={"message": "email me a summary", "session_id": session},
            headers=CUST,
        )
        return session

    def test_it_returns_the_message_that_was_actually_sent(self, client):
        session = self._send_summary(client)
        body = client.get(f"/dashboard/emails/{session}", headers=OPS).json()

        assert body["recipient"] == "ayesha.k@example.com"
        assert "#a855f7" in body["body_html"]  # the real themed markup
        assert body["feedback_token"] in body["body_html"]
        assert body["status"] in {"recorded", "sent"}

    def test_a_conversation_with_no_summary_is_404(self, client):
        assert (
            client.get("/dashboard/emails/never-happened", headers=OPS).status_code
            == 404
        )

    def test_a_customer_cannot_read_it(self, client):
        session = self._send_summary(client, "prev2")
        assert client.get(f"/dashboard/emails/{session}", headers=CUST).status_code == 403

    def test_another_tenant_cannot_read_it(self, client):
        """Same session id, different business — the lookup is tenant-scoped."""
        session = self._send_summary(client, "shared-session")
        assert (
            client.get(f"/dashboard/emails/{session}", headers=OTHER).status_code
            in {403, 404}
        )
