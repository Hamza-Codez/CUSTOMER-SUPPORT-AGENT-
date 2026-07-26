"""HTTP surface tests — the frozen /health and /chat contracts."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

AUTH = {"Authorization": "Bearer demo-token"}


@pytest.fixture
def client(store):
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_reports_provider_and_store(self, client):
        body = client.get("/health").json()
        assert body == {
            "status": "ok",
            "provider": "mock",
            "store": "mock",
            "db": "up",
        }

    def test_needs_no_auth(self, client):
        """Health must work before you have credentials — that is its job."""
        assert client.get("/health").status_code == 200


class TestChatAuth:
    def test_rejects_missing_token(self, client):
        r = client.post("/chat", json={"message": "hi"})
        assert r.status_code == 401
        assert "bearer" in r.json()["detail"].lower()

    def test_rejects_unknown_token(self, client):
        r = client.post(
            "/chat", json={"message": "hi"}, headers={"Authorization": "Bearer nope"}
        )
        assert r.status_code == 401

    def test_rejects_empty_message(self, client):
        r = client.post("/chat", json={"message": ""}, headers=AUTH)
        assert r.status_code == 422


class TestChatFlow:
    def test_full_lookup_returns_reply_and_action_chip(self, client):
        r = client.post(
            "/chat",
            json={
                "message": "where is ORD-1002? email ayesha.k@example.com",
                "session_id": "t1",
            },
            headers=AUTH,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["session_id"] == "t1"
        assert "ORD-1002" in body["reply"]
        assert body["actions"] == [
            {"kind": "order_looked_up", "label": "ORD-1002 · in transit", "ref": "ORD-1002"}
        ]

    def test_missing_details_asks_rather_than_guessing(self, client):
        body = client.post(
            "/chat",
            json={"message": "where is my order?", "session_id": "t2"},
            headers=AUTH,
        ).json()
        assert body["actions"] == []
        assert "order number" in body["reply"].lower()

    def test_identity_mismatch_surfaces_as_an_action(self, client):
        body = client.post(
            "/chat",
            json={
                "message": "ORD-1002 email attacker@example.com",
                "session_id": "t3",
            },
            headers=AUTH,
        ).json()
        assert body["actions"][0]["kind"] == "identity_check_failed"
        assert "FedEx" not in body["reply"]


class TestSessionMemory:
    def test_details_given_across_two_turns_are_remembered(self, client):
        """The order id arrives in turn one, the email in turn two."""
        first = client.post(
            "/chat",
            json={"message": "where is my order ORD-1002?", "session_id": "mem"},
            headers=AUTH,
        ).json()
        assert first["actions"] == []

        second = client.post(
            "/chat",
            json={"message": "ayesha.k@example.com", "session_id": "mem"},
            headers=AUTH,
        ).json()
        assert second["actions"][0]["kind"] == "order_looked_up"

    def test_a_new_session_id_starts_clean(self, client):
        client.post(
            "/chat",
            json={"message": "where is my order ORD-1002?", "session_id": "a"},
            headers=AUTH,
        )
        body = client.post(
            "/chat",
            json={"message": "ayesha.k@example.com", "session_id": "b"},
            headers=AUTH,
        ).json()
        # Session "b" never saw the order id, so nothing should be looked up.
        assert body["actions"] == []

    def test_sessions_are_isolated_between_tenants(self, client, store):
        """Same session_id, different businesses — memory must not be shared."""
        client.post(
            "/chat",
            json={"message": "where is my order ORD-1002?", "session_id": "shared"},
            headers={"Authorization": "Bearer demo-token"},
        )
        client.post(
            "/chat",
            json={"message": "hello", "session_id": "shared"},
            headers={"Authorization": "Bearer other-token"},
        )
        mine = await_sync(store.get_session_items("biz_demo", "shared"))
        theirs = await_sync(store.get_session_items("biz_other", "shared"))
        assert len(mine) == 2
        assert len(theirs) == 2
        assert "ORD-1002" not in str(theirs)


def await_sync(coro):
    """Run a coroutine from a sync test. Safe here: the mock store holds no loop-bound state."""
    import asyncio

    return asyncio.run(coro)
