"""In-memory mock backend — the zero-setup default.

This lets the whole agent run end-to-end with NO external services.
`store/supabase_store.py` implements the same functions against Postgres.
"""
from __future__ import annotations

import copy
import itertools
import re
from datetime import datetime, timedelta, timezone
from typing import Optional


def _utcnow() -> datetime:
    """Naive UTC now — keeps timestamps rendering as ISO-8601 + 'Z' (SPEC §4)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Knowledge base (stands in for the pgvector store) -----------------------
# The same five documents seed `kb_docs` in Supabase, so the demo is identical
# on both backends and any behaviour change is provably the swap, not content.
KNOWLEDGE_BASE = [
    {
        "title": "Shipping times",
        "body": "Standard shipping takes 3-5 business days. Express shipping takes "
                "1-2 business days. We ship worldwide.",
    },
    {
        "title": "Refund policy",
        "body": "Items can be refunded within 30 days of delivery if unused and in "
                "original packaging. Refunds are processed to the original payment "
                "method within 5-7 business days.",
    },
    {
        "title": "Product: AeroDesk Standing Desk",
        "body": "The AeroDesk is an electric height-adjustable standing desk. Height "
                "range 60-125cm, 100kg capacity, 3 memory presets. Available in oak "
                "and walnut. Price: $499.",
    },
    {
        "title": "Product: AeroChair Ergonomic Chair",
        "body": "The AeroChair has adjustable lumbar support, 4D armrests, and a "
                "breathable mesh back. Weight capacity 130kg. Price: $329.",
    },
    {
        "title": "Warranty",
        "body": "All furniture comes with a 5-year limited warranty covering "
                "manufacturing defects.",
    },
]

# --- Orders ------------------------------------------------------------------
ORDERS = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer": "Jordan Lee",
        "items": ["AeroDesk Standing Desk (oak)"],
        "total": 499.00,
        "status": "shipped",
        "carrier": "DHL",
        "tracking": "DHL-88231145",
        "eta": (_utcnow() + timedelta(days=2)).strftime("%Y-%m-%d"),
        "refundable": True,
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer": "Priya Nair",
        "items": ["AeroChair Ergonomic Chair"],
        "total": 329.00,
        "status": "delivered",
        "carrier": "FedEx",
        "tracking": "FDX-55190022",
        "eta": (_utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"),
        "refundable": True,
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer": "Sam Okoro",
        "items": ["AeroDesk Standing Desk (walnut)", "AeroChair Ergonomic Chair"],
        "total": 828.00,
        "status": "processing",
        "carrier": None,
        "tracking": None,
        "eta": (_utcnow() + timedelta(days=6)).strftime("%Y-%m-%d"),
        "refundable": False,  # not yet shipped -> refund handled differently
    },
}

# --- Tickets (created by the agent) ------------------------------------------
TICKETS: list[dict] = []
_ticket_counter = itertools.count(1)

# --- Conversation memory (the FTE's third trait) -----------------------------
# session_id -> serialized message dicts. Lost on restart; the Supabase backend
# persists the same shape to a table.
SESSIONS: dict[str, list[dict]] = {}

# --- Retrieval ---------------------------------------------------------------
# Words too common to signal relevance. Without this filter a substring match
# makes every question "hit" every article, and a KB miss can never be detected.
_STOPWORDS = {
    "the", "and", "for", "are", "you", "your", "our", "can", "does", "did", "was",
    "were", "with", "what", "when", "where", "why", "how", "this", "that", "there",
    "here", "please", "need", "want", "have", "has", "had", "will", "would", "about",
    "from", "get", "got", "any", "all", "not", "but", "its", "his", "her", "them",
    "they", "she", "hers", "him", "who", "whom", "been", "being", "into", "than",
    "then", "some", "much", "many", "just", "know", "tell", "let",
}

TOP_K = 3


def _tokens(text: str) -> set[str]:
    """Meaningful lowercase word tokens (>=3 chars, no stopwords)."""
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if len(w) >= 3 and w not in _STOPWORDS}


def get_order(order_id: str) -> Optional[dict]:
    return ORDERS.get(order_id.strip().upper())


def add_ticket(subject: str, detail: str, priority: str = "normal",
               escalated: bool = False, order_id: Optional[str] = None) -> dict:
    ticket = {
        "id": f"TCK-{next(_ticket_counter):04d}",
        "subject": subject,
        "detail": detail,
        "priority": priority,
        "escalated": escalated,
        "order_id": order_id,
        "status": "open",
        "created_at": _utcnow().isoformat(timespec="seconds") + "Z",
    }
    TICKETS.append(ticket)
    return ticket


def list_tickets() -> list[dict]:
    return list(reversed(TICKETS))  # newest first


def search_kb(query: str) -> list[dict]:
    """Keyword retrieval by token overlap. Supabase replaces this with pgvector
    cosine similarity — same signature, same `[{title, body}]` return shape.
    """
    q_tokens = _tokens(query)
    scored = []
    for doc in KNOWLEDGE_BASE:
        score = len(q_tokens & _tokens(doc["title"] + " " + doc["body"]))
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"title": d["title"], "body": d["body"]} for _, d in scored[:TOP_K]]


def get_session(session_id: str) -> list[dict]:
    # A deep copy, so callers can't mutate stored memory in place. Postgres
    # hands back a fresh row every read and this must behave the same — a
    # shallow copy still shares each message's nested `data` dict.
    return copy.deepcopy(SESSIONS.get(session_id, []))


def save_session(session_id: str, messages: list[dict]) -> None:
    SESSIONS[session_id] = copy.deepcopy(messages)


def clear_session(session_id: str) -> None:
    SESSIONS.pop(session_id, None)


def reset_tickets() -> None:
    """Clear the ticket log. Used by tests so each case starts from a clean audit trail."""
    global _ticket_counter
    TICKETS.clear()
    _ticket_counter = itertools.count(1)


def reset_sessions() -> None:
    """Clear all conversation memory. Tests only — mock backend has no equivalent
    on Supabase, where wiping every session wholesale is never a routine action."""
    SESSIONS.clear()
