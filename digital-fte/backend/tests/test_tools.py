"""Unit tests for the 5 tools, run directly against the mock store.

These prove the guardrails hold in CODE — independent of whatever the model
decides to say. If one of these fails, policy has regressed.
"""
from __future__ import annotations

import store
from tools import (create_ticket, escalate_to_human, process_refund, search_kb,
                   track_order)

# Text that must never reach a customer: operator-facing instructions.
OPERATOR_LEAKS = ["ask the customer", "do not refund", "escalate to a human",
                  "double-check it"]


def assert_customer_safe(text: str):
    lowered = text.lower()
    for leak in OPERATOR_LEAKS:
        assert leak not in lowered, f"operator instruction leaked to customer: {leak!r}"


# --- search_kb ---------------------------------------------------------------

def test_search_kb_returns_grounded_article_and_writes_no_ticket():
    result = search_kb.invoke({"query": "what is the refund policy"})
    assert "30 days of delivery" in result
    assert store.TICKETS == []


def test_search_kb_miss_escalates_in_code_and_invents_nothing():
    result = search_kb.invoke({"query": "do you offer gift wrapping"})

    assert len(store.TICKETS) == 1
    ticket = store.TICKETS[0]
    assert ticket["escalated"] is True
    assert ticket["priority"] == "high"
    assert "gift wrapping" in ticket["detail"]  # human gets full context

    assert ticket["id"] in result
    assert "can't answer" in result.lower()
    assert_customer_safe(result)


def test_search_kb_scoring_ignores_stopwords():
    """Substring matching on common words used to make every query a false hit."""
    assert "No knowledge-base article" in search_kb.invoke({"query": "is it a the"})


# --- track_order -------------------------------------------------------------

def test_track_order_returns_summary_for_known_order():
    result = track_order.invoke({"order_id": "ORD-1001"})
    assert "ORD-1001" in result
    assert "Jordan Lee" in result
    assert "DHL-88231145" in result
    assert store.TICKETS == []


def test_track_order_unknown_id_asks_to_recheck_without_escalating():
    result = track_order.invoke({"order_id": "ORD-9999"})
    assert "couldn't find" in result.lower()
    assert "double-check the id" in result.lower()
    assert store.TICKETS == []  # a typo is not a handoff
    assert_customer_safe(result)


# --- process_refund (the hard rule) -----------------------------------------

def test_refund_in_policy_is_approved_and_logged_once():
    result = process_refund.invoke({"order_id": "ORD-1002", "reason": "arrived damaged"})

    assert "329.00" in result
    assert len(store.TICKETS) == 1
    ticket = store.TICKETS[0]
    assert ticket["escalated"] is False           # approved, not escalated
    assert ticket["order_id"] == "ORD-1002"
    assert "arrived damaged" in ticket["detail"]
    assert ticket["id"] in result                 # auditable from the reply itself


def test_refund_out_of_policy_is_refused_and_escalated_in_code():
    result = process_refund.invoke({"order_id": "ORD-1003", "reason": "changed my mind"})

    # HARD RULE: no refund ticket of any kind was written.
    assert len(store.TICKETS) == 1
    ticket = store.TICKETS[0]
    assert ticket["escalated"] is True
    assert ticket["priority"] == "high"
    assert ticket["order_id"] == "ORD-1003"
    assert "No refund issued" in ticket["detail"]
    assert "changed my mind" in ticket["detail"]

    assert "haven't issued one" in result
    assert ticket["id"] in result
    assert_customer_safe(result)


def test_refund_unknown_order_refuses_without_writing_a_ticket():
    result = process_refund.invoke({"order_id": "ORD-9999", "reason": "damaged"})
    assert "couldn't find" in result.lower()
    assert store.TICKETS == []
    assert_customer_safe(result)


# --- create_ticket / escalate_to_human ---------------------------------------

def test_create_ticket_logs_with_given_priority():
    result = create_ticket.invoke(
        {"subject": "Assembly guide request", "detail": "Wants the AeroDesk manual",
         "priority": "low"}
    )
    assert len(store.TICKETS) == 1
    assert store.TICKETS[0]["priority"] == "low"
    assert store.TICKETS[0]["escalated"] is False
    assert store.TICKETS[0]["id"] in result


def test_escalate_to_human_creates_high_priority_flagged_ticket():
    result = escalate_to_human.invoke(
        {"summary": "Customer threatening legal action", "order_id": "ORD-1003"}
    )
    ticket = store.TICKETS[0]
    assert ticket["priority"] == "high"
    assert ticket["escalated"] is True
    assert ticket["order_id"] == "ORD-1003"
    assert "Customer threatening legal action" in ticket["detail"]
    assert ticket["id"] in result


def test_ticket_shape_matches_the_spec():
    escalate_to_human.invoke({"summary": "context", "order_id": ""})
    ticket = store.TICKETS[0]
    assert set(ticket) == {"id", "subject", "detail", "priority", "escalated",
                           "order_id", "user_id", "status", "created_at"}
    assert ticket["status"] == "open"
    assert ticket["order_id"] is None            # empty string normalised to null
    assert ticket["created_at"].endswith("Z")
    assert ticket["id"].startswith("TCK-")
