"""Conversation memory now lives in the data layer, not in the process.

Memory is the FTE's third trait (INTENT §2). These tests prove it is owned by
`store`, isolated per session, and survives the API layer being rebuilt — which
is what "persists across a restart" means once the backend is Postgres.
"""
from __future__ import annotations

import importlib
import json

import pytest
from fastapi.testclient import TestClient

import store
from fakes import FakeSupabase
from main import app
from store import mock_store, supabase_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean():
    mock_store.reset_sessions()
    mock_store.reset_tickets()
    yield
    mock_store.reset_sessions()
    mock_store.reset_tickets()


def chat(message: str, session_id: str) -> str:
    response = client.post("/chat", json={"message": message, "session_id": session_id})
    assert response.status_code == 200, response.text
    return response.json()["reply"]


# --- ownership ---------------------------------------------------------------

def test_the_api_module_no_longer_owns_conversation_state():
    """State has exactly one owner. If SESSIONS reappears in main, it has two."""
    import main
    assert not hasattr(main, "SESSIONS")


def test_a_turn_is_written_to_the_store():
    chat("what is your refund policy", "s1")

    stored = store.get_session("s1")
    assert stored, "the turn was not persisted"
    assert "refund policy" in json.dumps(stored).lower()


def test_memory_accumulates_across_turns():
    chat("what is your refund policy", "s1")
    first = len(store.get_session("s1"))
    chat("how long does shipping take", "s1")
    assert len(store.get_session("s1")) > first


def test_sessions_are_isolated():
    chat("what is your refund policy", "alice")
    chat("what is the warranty", "bob")

    assert "warranty" not in json.dumps(store.get_session("alice")).lower()
    assert "refund" not in json.dumps(store.get_session("bob")).lower()


def test_an_unknown_session_starts_empty():
    assert store.get_session("never-seen") == []


# --- durability --------------------------------------------------------------

def test_memory_survives_rebuilding_the_api_layer():
    """Stand-in for a restart: reload the API module and the agent singleton.
    Memory is in the store, so the conversation is still there afterwards."""
    chat("what is your refund policy", "durable")
    before = store.get_session("durable")

    import agent
    import main
    agent._agent = None
    importlib.reload(main)

    assert store.get_session("durable") == before
    assert TestClient(main.app).post(
        "/chat", json={"message": "and shipping?", "session_id": "durable"}
    ).status_code == 200
    assert len(store.get_session("durable")) > len(before)


def test_stored_messages_round_trip_through_json():
    """The Supabase column is jsonb — anything that won't serialise is lost."""
    chat("refund ORD-1002, it arrived damaged", "json")
    stored = store.get_session("json")

    assert json.loads(json.dumps(stored)) == stored
    kinds = {m["type"] for m in stored}
    assert {"human", "ai", "tool"} <= kinds, f"tool call not retained: {kinds}"


def test_clear_session_removes_only_that_session():
    chat("what is your refund policy", "keep")
    chat("what is your refund policy", "drop")

    store.clear_session("drop")
    assert store.get_session("drop") == []
    assert store.get_session("keep")


# --- backend parity ----------------------------------------------------------

@pytest.fixture(params=["mock", "supabase"])
def backend(request, monkeypatch):
    monkeypatch.setenv("DATA_BACKEND", request.param)
    if request.param == "supabase":
        supabase_store.set_client(FakeSupabase(mock_store.KNOWLEDGE_BASE))
    yield request.param
    supabase_store.set_client(None)


def test_session_contracts_behave_identically_on_both_backends(backend):
    assert store.get_session("parity") == []

    messages = [
        {"type": "human", "data": {"content": "refund ORD-1002", "type": "human"}},
        {"type": "ai", "data": {"content": "Refund approved.", "type": "ai"}},
    ]
    store.save_session("parity", messages)
    assert store.get_session("parity") == messages

    store.save_session("parity", messages[:1])       # overwrites, never appends
    assert store.get_session("parity") == messages[:1]

    store.clear_session("parity")
    assert store.get_session("parity") == []


def test_stored_sessions_are_snapshots_not_live_references(backend):
    """Postgres hands back a fresh row each read; the mock must not hand back
    the list it is storing, or callers could mutate memory in place."""
    store.save_session("snap", [{"type": "human", "data": {"content": "hi"}}])

    fetched = store.get_session("snap")
    fetched.append({"type": "ai", "data": {"content": "injected"}})
    fetched[0]["data"]["content"] = "tampered"

    assert store.get_session("snap") == [{"type": "human", "data": {"content": "hi"}}]
