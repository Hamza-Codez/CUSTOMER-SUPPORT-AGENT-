"""Full-flow integration tests over HTTP, on MODEL_PROVIDER=mock.

Covers the six scenarios SPEC §10 requires — KB answer, order track, valid
refund, invalid refund refusal, angry-case escalation, ticket-log correctness —
plus the API error contract. No API key, no network.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import main
import model
import store
from authed import authed_client, session_key
from main import app
from store import mock_store

client = authed_client(app)

# Internal plumbing that must never surface in a customer-facing reply.
REPLY_LEAKS = ["here's what i found", "[refund policy]", "[shipping times]",
               "ask the customer", "do not refund", "traceback"]


def chat(message: str, session_id: str = "test") -> str:
    response = client.post("/chat", json={"message": message, "session_id": session_id})
    assert response.status_code == 200, response.text
    reply = response.json()["reply"]
    lowered = reply.lower()
    for leak in REPLY_LEAKS:
        assert leak not in lowered, f"internal text leaked into reply: {leak!r}"
    return reply


# --- contract ----------------------------------------------------------------

def test_health_reports_the_live_provider_and_store():
    body = client.get("/health").json()
    assert body == {"status": "ok", "provider": "mock", "data": "mock", "auth": "mock"}


def test_chat_response_shape_matches_the_spec():
    body = client.post("/chat", json={"message": "hello", "session_id": "s1"}).json()
    assert set(body) == {"reply", "session_id", "provider"}
    assert body["session_id"] == "s1"
    assert body["provider"] == "mock"
    assert body["reply"].strip()


def test_chat_rejects_an_invalid_body_with_422():
    assert client.post("/chat", json={"session_id": "s1"}).status_code == 422


# --- the six verified scenarios ---------------------------------------------

def test_scenario_kb_answer_is_grounded_and_creates_no_ticket():
    reply = chat("what is your refund policy", "kb")
    assert "30 days" in reply
    assert client.get("/tickets").json()["tickets"] == []


def test_scenario_track_order():
    reply = chat("where is ORD-1001", "track")
    assert "ORD-1001" in reply
    assert "DHL-88231145" in reply
    assert client.get("/tickets").json()["tickets"] == []


def test_scenario_valid_refund_is_approved_and_appears_on_the_dashboard():
    reply = chat("please refund ORD-1002, it arrived damaged", "refund-ok")
    assert "329.00" in reply

    tickets = client.get("/tickets").json()["tickets"]
    assert len(tickets) == 1
    assert tickets[0]["escalated"] is False
    assert tickets[0]["order_id"] == "ORD-1002"
    assert tickets[0]["id"] in reply


def test_scenario_invalid_refund_is_refused_and_escalated():
    reply = chat("refund ORD-1003 please", "refund-bad")

    assert "haven't issued one" in reply
    tickets = client.get("/tickets").json()["tickets"]
    assert len(tickets) == 1                     # the escalation, and nothing else
    assert tickets[0]["escalated"] is True
    assert tickets[0]["priority"] == "high"
    assert "No refund issued" in tickets[0]["detail"]


def test_scenario_angry_case_escalates_high_priority():
    reply = chat("This is unacceptable, I want to speak to a manager about ORD-1003",
                 "angry")

    tickets = client.get("/tickets").json()["tickets"]
    assert len(tickets) == 1
    assert tickets[0]["escalated"] is True
    assert tickets[0]["priority"] == "high"
    assert tickets[0]["order_id"] == "ORD-1003"
    assert "manager" in tickets[0]["detail"]     # full context for the human
    assert tickets[0]["id"] in reply


def test_scenario_kb_miss_says_so_and_escalates_without_inventing():
    reply = chat("do you offer gift wrapping", "kb-miss")

    assert "can't answer" in reply.lower()
    tickets = client.get("/tickets").json()["tickets"]
    assert len(tickets) == 1
    assert tickets[0]["escalated"] is True


def test_scenario_ticket_log_is_newest_first_and_correctly_shaped():
    chat("refund ORD-1002, damaged", "log")
    chat("this is unacceptable", "log")

    tickets = client.get("/tickets").json()["tickets"]
    assert [t["id"] for t in tickets] == ["TCK-0002", "TCK-0001"]   # newest first
    assert set(tickets[0]) == {"id", "subject", "detail", "priority", "escalated",
                               "order_id", "user_id", "status", "created_at"}


# --- failure paths -----------------------------------------------------------

def test_unknown_order_asks_the_customer_to_recheck_without_escalating():
    reply = chat("track ORD-9999", "unknown")
    assert "couldn't find" in reply.lower()
    assert client.get("/tickets").json()["tickets"] == []


def test_agent_failure_returns_a_clean_500_envelope(monkeypatch):
    def boom():
        raise RuntimeError("model exploded")

    monkeypatch.setattr(main, "get_agent", boom)
    response = client.post("/chat", json={"message": "hi", "session_id": "boom"})

    assert response.status_code == 500
    assert "temporarily unavailable" in response.json()["detail"]
    assert "model exploded" not in response.text          # no internals leaked
    assert store.get_session(session_key("boom")) == []                # failed turn not retained


class _FakeApiError(Exception):
    """Shaped like postgrest.exceptions.APIError: carries a `code`."""
    def __init__(self, code):
        super().__init__(f"Could not find the table 'public.tickets'")
        self.code = code


def test_an_unprovisioned_database_returns_503_with_instructions(monkeypatch):
    """A missing table used to escape as a raw 500 with a stack trace."""
    monkeypatch.setattr(mock_store, "list_tickets",
                        lambda: (_ for _ in ()).throw(_FakeApiError("PGRST205")))

    response = client.get("/tickets")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "0001_init.sql" in detail
    assert "DATA_BACKEND=mock" in detail
    assert "Traceback" not in response.text


def test_an_unreachable_database_returns_503_without_leaking_internals(monkeypatch):
    monkeypatch.setattr(mock_store, "list_tickets",
                        lambda: (_ for _ in ()).throw(OSError("connection refused to 10.0.0.5")))

    response = client.get("/tickets")

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]
    assert "10.0.0.5" not in response.text        # no host details leaked


def test_chat_survives_an_unprovisioned_database(monkeypatch):
    monkeypatch.setattr(mock_store, "get_session",
                        lambda _s: (_ for _ in ()).throw(_FakeApiError("PGRST205")))

    response = client.post("/chat", json={"message": "hi", "session_id": "s"})
    assert response.status_code == 503
    assert "0001_init.sql" in response.json()["detail"]


def test_unknown_provider_raises_a_clear_value_error(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "bogus")
    with pytest.raises(ValueError, match="Unknown MODEL_PROVIDER"):
        model.get_model()


# --- memory (the FTE's third trait) ------------------------------------------

def test_sessions_do_not_leak_into_each_other():
    chat("what is your refund policy", "alice")
    chat("what is your warranty", "bob")

    alice = json.dumps(store.get_session(session_key("alice")))
    assert "warranty" not in alice.lower()
    assert store.get_session(session_key("bob"))


def test_memory_accumulates_within_one_session():
    chat("what is your refund policy", "memo")
    first = len(store.get_session(session_key("memo")))
    chat("what about shipping times", "memo")
    assert len(store.get_session(session_key("memo"))) > first


@pytest.fixture(autouse=True)
def clean_sessions():
    mock_store.reset_sessions()
    yield
    mock_store.reset_sessions()
    mock_store.reset_tickets()
