"""Prove a real Supabase project satisfies the store contracts.

    cd backend
    DATA_BACKEND=supabase python scripts/verify_supabase.py

Runs the same checks the parity tests run against the fake client, but against
your project. It writes two tickets (one refund, one escalation) — that is the
point, they must survive a restart — and prints the ticket IDs so you can see
them on the dashboard.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402,F401  — loads .env

import store                            # noqa: E402
from tools import process_refund, search_kb, track_order   # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []

# Postgres/PostgREST failures we can translate into an instruction.
HINTS = {
    "PGRST205": "table missing — run db/migrations/0001_init.sql, 0002_seed_orders.sql, 0003_sessions.sql",
    "PGRST202": "function missing — run db/migrations/0001_init.sql (it creates match_kb_docs)",
    "42P01": "table missing — run the migrations in db/migrations/",
    "42883": "function or the vector extension missing — run 0001_init.sql",
}


def check(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append((name, passed, detail))
    print(f"  {'PASS' if passed else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))


def attempt(name: str, fn, *, hint: str = ""):
    """Run a probe. A driver error is a FAILED CHECK, not a traceback — this
    script exists to diagnose a fresh project, so it has to survive one."""
    try:
        return fn()
    except Exception as exc:
        code = getattr(exc, "code", None) or ""
        message = str(getattr(exc, "message", None) or exc)
        check(name, False, HINTS.get(code) or hint or message[:120])
        return None


def _diagnose_empty_search() -> str:
    """Say WHY the KB looks empty, instead of guessing "run ingest_kb.py".

    An empty result has two very different causes: nothing was loaded, or plenty
    was loaded and the index never returns it. Telling them apart needs a look at
    the raw rows and the unfiltered similarities.
    """
    from store import supabase_store
    import embeddings

    try:
        client = supabase_store.get_client()
        rows = client.table("kb_docs").select("id,embedding").execute().data or []
    except Exception as exc:                        # noqa: BLE001
        return f"could not read kb_docs ({type(exc).__name__})"

    if not rows:
        return "kb_docs is empty — run scripts/ingest_kb.py"

    embedded = sum(1 for r in rows if r.get("embedding"))
    if not embedded:
        return f"{len(rows)} rows but no embeddings — re-run scripts/ingest_kb.py"

    try:
        raw = client.rpc("match_kb_docs", {
            "query_embedding": embeddings.embed_query("what is your refund policy"),
            "match_count": 5,
            "min_similarity": -1.0,
        }).execute().data or []
    except Exception as exc:                        # noqa: BLE001
        return f"match_kb_docs failed ({type(exc).__name__})"

    if raw:
        best = max(r["similarity"] for r in raw)
        return (f"{embedded} embedded rows, best similarity {best:.3f} — below the "
                f"0.05 threshold. Re-embed with the provider you query with.")

    return (f"{embedded} embedded rows, but the RPC returns nothing even unfiltered "
            f"— the vector index is not serving them. Apply "
            f"db/migrations/0005_fix_vector_index.sql (python scripts/apply_schema.py).")


def main() -> int:
    print(f"Backend: {store.backend_name()}\n")

    print("Orders")
    order = attempt("get_order returns a row", lambda: store.get_order("ORD-1001"),
                    hint="run migrations 0001 + 0002 first")
    if order:
        check("total is a float", isinstance(order["total"], float), repr(order["total"]))
        check("items is a list", isinstance(order["items"], list), repr(order["items"]))
        check("refundable is a bool", isinstance(order["refundable"], bool))
        check("unknown id returns None", store.get_order("ORD-9999") is None)

    print("\nKnowledge base (pgvector)")
    docs = attempt("kb_docs is queryable",
                   lambda: store.search_kb("what is your refund policy"))
    if docs is not None:
        check("kb_docs is queryable", True)
        check("vector search returns a hit", bool(docs),
              docs[0]["title"] if docs else _diagnose_empty_search())
        check("a miss returns []", store.search_kb("do you offer gift wrapping") == [])

    print("\nTickets (audit trail)")
    refund = refused = "(not run)"
    before = attempt("ticket log is readable", lambda: len(store.list_tickets()))
    if before is not None and order:
        refund = process_refund.invoke({"order_id": "ORD-1002", "reason": "verify script"})
        refused = process_refund.invoke({"order_id": "ORD-1003", "reason": "verify script"})
        after = store.list_tickets()

        check("refund wrote a ticket", len(after) == before + 2)
        check("newest first", after[0]["created_at"] >= after[-1]["created_at"])
        check("created_at is ISO-8601 Z", after[0]["created_at"].endswith("Z"),
              after[0]["created_at"])
        check("out-of-policy refund refused", "haven't issued one" in refused)
        check("refusal escalated", any(t["escalated"] and t["order_id"] == "ORD-1003"
                                       for t in after[:2]))

    print("\nSessions (conversation memory)")
    probe = [{"type": "human", "data": {"content": "verify script", "type": "human"}}]

    def round_trip():
        store.save_session("verify-script", probe)
        return store.get_session("verify-script")

    stored = attempt("session round-trips", round_trip,
                     hint="run db/migrations/0003_sessions.sql")
    if stored is not None:
        check("session round-trips", stored == probe)
        store.clear_session("verify-script")
        check("session clears", store.get_session("verify-script") == [])

    if order:
        print("\nGuardrail replies")
        print(f"  refund   : {refund}")
        print(f"  refused  : {refused}")
        print(f"  unknown  : {track_order.invoke({'order_id': 'ORD-9999'})}")
        print(f"  kb miss  : {search_kb.invoke({'query': 'do you offer gift wrapping'})}")

    failed = [name for name, passed, _ in CHECKS if not passed]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed.")
    if failed:
        print("Failed: " + ", ".join(failed))
        return 1
    print("Supabase satisfies the store contracts. Tickets above persist across restarts.")
    return 0


if __name__ == "__main__":
    if os.getenv("DATA_BACKEND", "mock").lower() != "supabase":
        print("Set DATA_BACKEND=supabase before verifying.", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(main())
