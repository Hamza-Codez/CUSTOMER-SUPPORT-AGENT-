"""Backend parity: the SAME assertions run against mock and Supabase.

This is what makes the swap safe. If Postgres's numeric-as-string or
timestamptz-with-offset ever reached the tools, these fail — because the mock
backend's assertions are the specification.

The Supabase side runs against `tests/fakes.FakeSupabase`, so no credentials
are needed. Real-project verification is `scripts/verify_supabase.py`.
"""
from __future__ import annotations

import pytest

import store
from fakes import FakeSupabase
from store import mock_store, supabase_store

TICKET_FIELDS = {"id", "subject", "detail", "priority", "escalated",
                 "order_id", "user_id", "status", "created_at"}
ORDER_FIELDS = {"order_id", "customer", "items", "total", "status",
                "carrier", "tracking", "eta", "refundable", "user_id"}


@pytest.fixture(params=["mock", "supabase"])
def backend(request, monkeypatch):
    """Point the store facade at each backend in turn."""
    monkeypatch.setenv("DATA_BACKEND", request.param)
    if request.param == "supabase":
        supabase_store.set_client(FakeSupabase(mock_store.KNOWLEDGE_BASE))
    yield request.param
    supabase_store.set_client(None)


# --- orders ------------------------------------------------------------------

def test_get_order_returns_the_spec_shape_with_the_spec_types(backend):
    order = store.get_order("ORD-1001")

    assert set(order) == ORDER_FIELDS
    assert order["order_id"] == "ORD-1001"
    assert order["customer"] == "Jordan Lee"
    assert isinstance(order["total"], float) and order["total"] == 499.00
    assert isinstance(order["items"], list) and order["items"][0].startswith("AeroDesk")
    assert isinstance(order["refundable"], bool) and order["refundable"] is True
    assert len(order["eta"]) == 10 and order["eta"][4] == "-"


def test_get_order_normalises_the_id(backend):
    assert store.get_order("  ord-1002 ")["order_id"] == "ORD-1002"


def test_get_order_returns_none_when_unknown(backend):
    assert store.get_order("ORD-9999") is None


def test_the_out_of_policy_order_is_out_of_policy_on_both_backends(backend):
    """The hard rule depends on this flag surviving the swap."""
    assert store.get_order("ORD-1003")["refundable"] is False
    assert store.get_order("ORD-1002")["refundable"] is True


# --- tickets -----------------------------------------------------------------

def test_add_ticket_returns_the_spec_shape(backend):
    ticket = store.add_ticket("Refund issued for ORD-1002", "Reason: damaged",
                              priority="normal", order_id="ORD-1002")

    assert set(ticket) == TICKET_FIELDS
    assert ticket["id"].startswith("TCK-")
    assert ticket["status"] == "open"
    assert ticket["escalated"] is False
    assert ticket["order_id"] == "ORD-1002"
    assert ticket["created_at"].endswith("Z")
    assert "+00:00" not in ticket["created_at"]      # timestamptz was coerced
    assert len(ticket["created_at"]) == 20           # YYYY-MM-DDTHH:MM:SSZ


def test_escalated_ticket_keeps_its_flags(backend):
    ticket = store.add_ticket("ESCALATION: needs human review", "context",
                              priority="high", escalated=True, order_id="ORD-1003")
    assert ticket["escalated"] is True
    assert ticket["priority"] == "high"


def test_list_tickets_is_newest_first(backend):
    store.add_ticket("first", "a")
    store.add_ticket("second", "b")
    store.add_ticket("third", "c")

    subjects = [t["subject"] for t in store.list_tickets()]
    assert subjects == ["third", "second", "first"]


def test_list_tickets_starts_empty(backend):
    assert store.list_tickets() == []


# --- knowledge base ----------------------------------------------------------

def test_search_kb_returns_title_body_dicts(backend):
    docs = store.search_kb("what is your refund policy")

    assert docs, "expected at least one match"
    assert set(docs[0]) == {"title", "body"}          # similarity is not exposed
    assert docs[0]["title"] == "Refund policy"
    assert "30 days of delivery" in docs[0]["body"]


@pytest.mark.parametrize("query,expected", [
    ("how long does shipping take", "Shipping times"),
    ("tell me about the AeroChair", "Product: AeroChair Ergonomic Chair"),
    ("what is the warranty", "Warranty"),
])
def test_search_kb_ranks_the_right_article_first(backend, query, expected):
    assert store.search_kb(query)[0]["title"] == expected


def test_search_kb_returns_empty_on_a_miss(backend):
    """The empty list is what makes tools.search_kb escalate — on both backends."""
    assert store.search_kb("do you offer gift wrapping") == []


def test_search_kb_returns_at_most_three(backend):
    assert len(store.search_kb("desk chair shipping refund warranty")) <= 3


# --- backend selection & safety ---------------------------------------------

def test_unknown_backend_raises_a_clear_value_error(monkeypatch):
    monkeypatch.setenv("DATA_BACKEND", "mysql")
    with pytest.raises(ValueError, match="Unknown DATA_BACKEND"):
        store.list_tickets()


def test_supabase_without_credentials_raises_a_clear_value_error(monkeypatch):
    monkeypatch.setenv("DATA_BACKEND", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    supabase_store.set_client(None)

    with pytest.raises(ValueError, match="SUPABASE_URL"):
        store.get_order("ORD-1001")


def test_supabase_refuses_to_wipe_the_audit_trail(monkeypatch):
    monkeypatch.setenv("DATA_BACKEND", "supabase")
    supabase_store.set_client(FakeSupabase(mock_store.KNOWLEDGE_BASE))
    try:
        with pytest.raises(RuntimeError, match="audit log is not disposable"):
            store.reset_tickets()
    finally:
        supabase_store.set_client(None)


def test_backend_name_reports_what_is_live(backend):
    assert store.backend_name() == backend
