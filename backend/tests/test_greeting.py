"""The opening turn.

Reported from actually using the demo: typing "Hi" produced "I can't confirm
that from your documents". Nothing was broken — the Orchestrator is pinned to
`tool_choice="required"`, its only tools were handoffs, so a greeting was forced
into a specialist and Support ran retrieval on the word "hi".

These tests pin the fix and, more importantly, its edges: a greeting must not
become a way to get an ungrounded answer, and a message that merely *starts*
with hello must still route.
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


def send(client, message: str, session_id: str) -> dict:
    r = client.post(
        "/chat", json={"message": message, "session_id": session_id}, headers=AUTH
    )
    assert r.status_code == 200, r.text
    return r.json()


def kinds(body: dict) -> list[str]:
    return [a["kind"] for a in body["actions"]]


class TestGreeting:
    @pytest.mark.parametrize(
        "message",
        ["Hi", "hi", "Hello", "hey there", "Good morning", "thanks", "what can you do"],
    )
    def test_a_greeting_is_greeted(self, client, message):
        body = send(client, message, session_id=f"greet-{message}")
        assert "greeted" in kinds(body)
        # Not the retrieval-miss answer, which is what this replaced.
        assert "can't confirm" not in body["reply"].lower()
        assert "cannot confirm" not in body["reply"].lower()

    def test_the_greeting_names_the_store_and_what_it_can_do(self, client):
        body = send(client, "hi", session_id="greet-content")
        reply = body["reply"].lower()
        assert "aeron home goods" in reply
        assert "order" in reply and "refund" in reply

    def test_a_greeting_never_routes_to_a_specialist(self, client):
        body = send(client, "hello", session_id="greet-noroute")
        assert "routed" not in kinds(body)

    @pytest.mark.parametrize(
        "message,expected",
        [
            ("hi, where is my order ORD-1002?", "Orders"),
            ("hello, I want a refund", "Refunds"),
            ("hey, how long does dispatch take?", "Support"),
        ],
    )
    def test_a_greeting_carrying_a_request_still_routes(self, client, message, expected):
        """The bug this could easily have become: swallowing real questions."""
        body = send(client, message, session_id=f"greet-plus-{expected}")
        refs = [a["ref"] for a in body["actions"] if a["kind"] == "routed"]
        assert refs == [expected]
        assert "greeted" not in kinds(body)

    def test_greeting_does_not_unlock_an_ungrounded_answer(self, client):
        """A greeting, then a real question in the same session.

        The second turn must still be grounded — the greeting in the first turn
        must not read as evidence for it.
        """
        send(client, "hi", session_id="greet-then-ask")
        body = send(client, "how long does dispatch take?", session_id="greet-then-ask")
        assert "policy_cited" in kinds(body)
