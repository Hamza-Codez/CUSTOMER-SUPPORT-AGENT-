"""In-memory mock data store.

This lets the whole agent run end-to-end with ZERO external setup.
Swap these functions for Supabase / a real DB later without touching the agent.
"""
from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone
from typing import Optional


def _utcnow() -> datetime:
    """Naive UTC now — keeps timestamps rendering as ISO-8601 + 'Z' (SPEC §4)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Knowledge base (stands in for a RAG vector store) -----------------------
# In production, replace `search_kb` with a Pinecone / pgvector similarity search.
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


def reset_tickets() -> None:
    """Clear the ticket log. Used by tests so each case starts from a clean audit trail."""
    global _ticket_counter
    TICKETS.clear()
    _ticket_counter = itertools.count(1)
