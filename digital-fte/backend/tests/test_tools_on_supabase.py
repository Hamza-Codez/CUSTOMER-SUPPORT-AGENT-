"""The Phase 1 guardrails, re-run against the Supabase backend.

The tools are not modified and not aware of the swap. If the store contracts
held, policy holds too — a refund still can't escape the code check, and a KB
miss still escalates. This is the acceptance test for the whole phase.
"""
from __future__ import annotations

import pytest

import store
from fakes import FakeSupabase
from store import mock_store, supabase_store
from tools import process_refund, search_kb, track_order


@pytest.fixture(autouse=True)
def supabase_backend(monkeypatch):
    monkeypatch.setenv("DATA_BACKEND", "supabase")
    supabase_store.set_client(FakeSupabase(mock_store.KNOWLEDGE_BASE))
    yield
    supabase_store.set_client(None)


def test_valid_refund_is_approved_and_persisted(supabase_backend):
    result = process_refund.invoke({"order_id": "ORD-1002", "reason": "arrived damaged"})

    assert "329.00" in result
    tickets = store.list_tickets()
    assert len(tickets) == 1
    assert tickets[0]["escalated"] is False
    assert tickets[0]["order_id"] == "ORD-1002"
    assert tickets[0]["id"] in result


def test_out_of_policy_refund_is_still_refused_and_escalated(supabase_backend):
    """The hard rule survives the database swap."""
    result = process_refund.invoke({"order_id": "ORD-1003", "reason": "changed my mind"})

    tickets = store.list_tickets()
    assert len(tickets) == 1                       # the escalation, and nothing else
    assert tickets[0]["escalated"] is True
    assert tickets[0]["priority"] == "high"
    assert "No refund issued" in tickets[0]["detail"]
    assert "haven't issued one" in result


def test_kb_hit_answers_from_stored_content(supabase_backend):
    result = search_kb.invoke({"query": "what is your refund policy"})
    assert "30 days of delivery" in result
    assert store.list_tickets() == []


def test_kb_miss_still_escalates_via_vector_search(supabase_backend):
    result = search_kb.invoke({"query": "do you offer gift wrapping"})

    tickets = store.list_tickets()
    assert len(tickets) == 1
    assert tickets[0]["escalated"] is True
    assert "gift wrapping" in tickets[0]["detail"]
    assert "can't answer" in result.lower()


def test_unknown_order_still_asks_to_recheck_without_escalating(supabase_backend):
    result = track_order.invoke({"order_id": "ORD-9999"})
    assert "double-check the id" in result.lower()
    assert store.list_tickets() == []


def test_tracking_a_real_order_renders_identically(supabase_backend):
    result = track_order.invoke({"order_id": "ORD-1001"})
    assert "Total: $499.00" in result               # numeric coerced, not "499.00" str
    assert "DHL-88231145" in result
