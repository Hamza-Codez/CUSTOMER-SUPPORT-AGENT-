"""In-memory mock backend — the zero-setup default.

This lets the whole agent run end-to-end with NO external services.
`store/supabase_store.py` implements the same functions against Postgres.
"""
from __future__ import annotations

import copy
import itertools
import re

import knowledge
from datetime import datetime, timedelta, timezone
from typing import Optional


def _utcnow() -> datetime:
    """Naive UTC now — keeps timestamps rendering as ISO-8601 + 'Z' (SPEC §4)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Knowledge base ----------------------------------------------------------
# Loaded from real documents in `db/knowledge/` — edit those files, not this
# list. The same passages seed `kb_docs` in Supabase, so the demo is identical
# on both backends and any behaviour change is provably the swap, not content.
#
# The literal below is only a fallback for an empty/missing folder, so the app
# still runs end to end out of the box.
_FALLBACK_KNOWLEDGE = [
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

# Real documents win; the literal above is only used if the folder is empty.
KNOWLEDGE_BASE = knowledge.load_documents() or _FALLBACK_KNOWLEDGE


def reload_knowledge() -> int:
    """Re-read db/knowledge/ without restarting. Returns the passage count."""
    global KNOWLEDGE_BASE
    KNOWLEDGE_BASE = knowledge.load_documents() or _FALLBACK_KNOWLEDGE
    return len(KNOWLEDGE_BASE)


# --- Orders ------------------------------------------------------------------
# `user_id: None` marks a shared demo fixture — the three canonical orders the
# docs and tests refer to by name. Orders created by `seed_demo_orders` carry a
# real owner and are visible only to them.
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
        "user_id": None,
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
        "user_id": None,
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
        "user_id": None,
    },
}

# What a new signup gets: the same three shapes (one shipped, one delivered and
# refundable, one processing and NOT refundable) so onboarding can demonstrate
# both the approval and the refusal. `_eta_days` is resolved at seed time.
_DEMO_ORDER_TEMPLATES = [
    {"customer": "You", "items": ["AeroDesk Standing Desk (oak)"], "total": 499.00,
     "status": "shipped", "carrier": "DHL", "tracking": "DHL-88231145",
     "refundable": True, "_eta_days": 2},
    {"customer": "You", "items": ["AeroChair Ergonomic Chair"], "total": 329.00,
     "status": "delivered", "carrier": "FedEx", "tracking": "FDX-55190022",
     "refundable": True, "_eta_days": -1},
    {"customer": "You", "items": ["AeroDesk Standing Desk (walnut)"], "total": 828.00,
     "status": "processing", "carrier": None, "tracking": None,
     "refundable": False, "_eta_days": 6},
]

# Seeded ids start well clear of the canonical 1001-1003 so they never collide.
_order_counter = itertools.count(2001)

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


def owns(order: dict, user_id: Optional[str]) -> bool:
    """An order with `user_id: None` is a shared demo fixture, visible to anyone.
    An owned order is visible only to its owner — that is the whole rule."""
    return order.get("user_id") is None or order["user_id"] == user_id


def get_order(order_id: str, user_id: Optional[str] = None) -> Optional[dict]:
    order = ORDERS.get(order_id.strip().upper())
    if order is None or not owns(order, user_id):
        # Someone else's order is reported as "not found", never as "forbidden":
        # a 403 here would confirm the id exists and leak the ordering pattern.
        return None
    return order


def add_ticket(subject: str, detail: str, priority: str = "normal",
               escalated: bool = False, order_id: Optional[str] = None,
               user_id: Optional[str] = None) -> dict:
    ticket = {
        "id": f"TCK-{next(_ticket_counter):04d}",
        "subject": subject,
        "detail": detail,
        "priority": priority,
        "escalated": escalated,
        "order_id": order_id,
        "user_id": user_id,
        "status": "open",
        "created_at": _utcnow().isoformat(timespec="seconds") + "Z",
    }
    TICKETS.append(ticket)
    return ticket


def seed_demo_orders(user_id: str) -> list[dict]:
    """Give a new signup their own copy of the demo orders (onboarding).

    IDs are globally unique, so `order_id` stays a primary key and the
    tickets→orders reference survives. Re-running is a no-op.
    """
    existing = [o for o in ORDERS.values() if o.get("user_id") == user_id]
    if existing:
        return sorted(existing, key=lambda o: o["order_id"])

    seeded = []
    for template in _DEMO_ORDER_TEMPLATES:
        order = dict(template)
        order["order_id"] = f"ORD-{next(_order_counter):04d}"
        order["user_id"] = user_id
        order["eta"] = (_utcnow() + timedelta(days=template["_eta_days"])).strftime("%Y-%m-%d")
        order.pop("_eta_days")
        ORDERS[order["order_id"]] = order
        seeded.append(order)
    return seeded


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


def reset_orders() -> None:
    """Drop every seeded order, keeping the three shared demo fixtures. Tests only."""
    global _order_counter
    for order_id in [k for k, v in ORDERS.items() if v.get("user_id") is not None]:
        del ORDERS[order_id]
    _order_counter = itertools.count(2001)


def reset_sessions() -> None:
    """Clear all conversation memory. Tests only — mock backend has no equivalent
    on Supabase, where wiping every session wholesale is never a routine action."""
    SESSIONS.clear()
