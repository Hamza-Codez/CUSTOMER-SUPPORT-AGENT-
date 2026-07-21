"""Supabase (Postgres + pgvector) backend.

Implements exactly the signatures `store/mock_store.py` proved, so the agent,
tools and API are unchanged by the swap.

    DATA_BACKEND=supabase
    SUPABASE_URL=https://<project>.supabase.co
    SUPABASE_SERVICE_KEY=<service_role key>       # server-side only, never in the browser

Postgres returns types JSON cannot express the way the mock does (numeric as a
string, timestamptz with a +00:00 offset). Every row is therefore coerced back
to the SPEC §4 shape before it leaves this module — that coercion is what the
parity tests police.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import embeddings

_client = None


def set_client(client) -> None:
    """Inject a client. Used by the parity tests to run without a real project."""
    global _client
    _client = client


def get_client():
    """Lazily build the Supabase client so the mock backend never needs the SDK."""
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError(
            "DATA_BACKEND=supabase requires SUPABASE_URL and SUPABASE_SERVICE_KEY "
            "(see backend/.env.example)."
        )
    try:
        from supabase import create_client
    except ImportError as exc:      # pragma: no cover - depends on optional extra
        raise ValueError(
            "DATA_BACKEND=supabase requires the 'supabase' package: "
            "pip install supabase"
        ) from exc

    _client = create_client(url, key)
    return _client


# --- shape coercion (parity with the mock store) -----------------------------

def _to_order(row: dict) -> dict:
    return {
        "order_id": row["order_id"],
        "customer": row["customer"],
        "items": list(row["items"] or []),
        "total": float(row["total"]),                    # numeric arrives as str
        "status": row["status"],
        "carrier": row.get("carrier"),
        "tracking": row.get("tracking"),
        "eta": str(row["eta"])[:10] if row.get("eta") else None,
        "refundable": bool(row["refundable"]),
    }


def _to_ticket(row: dict) -> dict:
    created = str(row["created_at"])
    # timestamptz -> the ISO-8601 'Z' form SPEC §4 requires.
    created = created.replace("+00:00", "").replace("Z", "")
    if "." in created:
        created = created.split(".")[0]
    return {
        "id": row["id"],
        "subject": row["subject"],
        "detail": row.get("detail"),
        "priority": row["priority"],
        "escalated": bool(row["escalated"]),
        "order_id": row.get("order_id"),
        "status": row["status"],
        "created_at": created + "Z",
    }


# --- the frozen interface ----------------------------------------------------

def get_order(order_id: str) -> Optional[dict]:
    rows = (get_client().table("orders")
            .select("*")
            .eq("order_id", order_id.strip().upper())
            .limit(1)
            .execute()).data
    return _to_order(rows[0]) if rows else None


def add_ticket(subject: str, detail: str, priority: str = "normal",
               escalated: bool = False, order_id: Optional[str] = None) -> dict:
    # `id` and `created_at` are omitted on purpose — Postgres generates both, so
    # concurrent workers can't collide on a TCK number.
    rows = (get_client().table("tickets")
            .insert({
                "subject": subject,
                "detail": detail,
                "priority": priority,
                "escalated": escalated,
                "order_id": order_id,
            })
            .execute()).data
    if not rows:
        raise RuntimeError("Ticket insert returned no row — the action was NOT logged.")
    return _to_ticket(rows[0])


def list_tickets() -> list[dict]:
    rows = (get_client().table("tickets")
            .select("*")
            .order("created_at", desc=True)
            .order("id", desc=True)          # deterministic within the same tick
            .execute()).data
    return [_to_ticket(r) for r in rows or []]


def search_kb(query: str) -> list[dict]:
    """pgvector cosine similarity via the match_kb_docs RPC.

    Returns the mock store's `[{title, body}]` shape — the similarity score is
    dropped here so upstream code cannot come to depend on it.
    """
    rows = (get_client().rpc("match_kb_docs", {
        "query_embedding": embeddings.embed_query(query),
        "match_count": 3,
    }).execute()).data
    return [{"title": r["title"], "body": r["body"]} for r in rows or []]


def get_session(session_id: str) -> list[dict]:
    rows = (get_client().table("sessions")
            .select("messages")
            .eq("session_id", session_id)
            .limit(1)
            .execute()).data
    return list(rows[0]["messages"] or []) if rows else []


def save_session(session_id: str, messages: list[dict]) -> None:
    # Upsert on the primary key: one row per session, rewritten each turn.
    # updated_at is sent explicitly — a column default only fires on INSERT, so
    # an upsert that updates would otherwise leave the timestamp stale.
    (get_client().table("sessions")
     .upsert({"session_id": session_id,
              "messages": messages,
              "updated_at": datetime.now(timezone.utc).isoformat()},
             on_conflict="session_id")
     .execute())


def clear_session(session_id: str) -> None:
    get_client().table("sessions").delete().eq("session_id", session_id).execute()


def reset_tickets() -> None:
    """Refused on purpose: this would wipe a real audit trail (INTENT §3)."""
    raise RuntimeError(
        "reset_tickets() is a mock-only test helper. Refusing to delete tickets "
        "from Supabase — the audit log is not disposable."
    )
