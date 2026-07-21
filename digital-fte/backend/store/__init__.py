"""The data layer's only public seam.

Everything upstream (tools, agent, API) calls `store.<fn>` and never learns
whether the answer came from a dict or from Postgres. The backend is chosen at
call time by env var, mirroring `model.get_model()`:

    DATA_BACKEND = mock | supabase        (default: mock)

Frozen interface — both backends implement these identically:

    get_order(order_id: str, user_id=None) -> dict | None   # scoped to the owner
    add_ticket(subject, detail, priority="normal", escalated=False,
               order_id=None, user_id=None) -> dict
    seed_demo_orders(user_id: str) -> list[dict]            # onboarding
    list_tickets() -> list[dict]                  # newest first
    search_kb(query: str) -> list[dict]           # [{title, body}], best first
    get_session(session_id: str) -> list[dict]    # serialized messages, [] if new
    save_session(session_id: str, messages: list[dict]) -> None
    clear_session(session_id: str) -> None
    reset_tickets() -> None                       # tests only

Sessions are stored as plain JSON dicts: the data layer never imports LangChain.
`main.py` converts with `messages_to_dict` / `messages_from_dict`.
"""
from __future__ import annotations

import functools
import importlib
import os
from typing import Optional

_BACKENDS = {"mock": ".mock_store", "supabase": ".supabase_store"}


class StoreUnavailable(Exception):
    """The data layer could not be reached, or isn't provisioned yet.

    Raised instead of letting a driver exception escape as a 500 with a stack
    trace. `main.py` turns this into a 503 carrying the instruction below.
    """


# PostgREST/Postgres codes that mean "the schema isn't set up", not "it broke".
_NOT_PROVISIONED = {"PGRST205", "PGRST202", "42P01", "42883"}
_RUN_MIGRATIONS = (
    "The database is not provisioned. Run db/migrations/0001_init.sql, "
    "0002_seed_orders.sql, 0003_sessions.sql and 0004_user_scoping.sql, "
    "or set DATA_BACKEND=mock to run without a database."
)


def _guard(fn):
    """Translate driver failures into StoreUnavailable, so no route can leak one.

    ValueError and RuntimeError pass through untouched: those are our own
    deliberate signals (bad config, refusing to wipe the audit log), and tests
    assert on them directly.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (ValueError, RuntimeError, StoreUnavailable):
            raise
        except Exception as exc:
            code = str(getattr(exc, "code", "") or "")
            if code in _NOT_PROVISIONED:
                raise StoreUnavailable(_RUN_MIGRATIONS) from exc
            raise StoreUnavailable(
                f"The data store is unavailable ({type(exc).__name__})."
            ) from exc
    return wrapper


def _backend():
    """Resolve the active backend module. Read per call so tests can switch it."""
    name = os.getenv("DATA_BACKEND", "mock").lower()
    if name not in _BACKENDS:
        raise ValueError(
            f"Unknown DATA_BACKEND '{name}' (use {' | '.join(_BACKENDS)})"
        )
    # import_module, not `from . import x` — the latter re-enters __getattr__
    # below while the submodule attribute is still unset, and recurses.
    return importlib.import_module(_BACKENDS[name], __name__)


def backend_name() -> str:
    """Which store is live — surfaced on /health alongside the model provider."""
    return os.getenv("DATA_BACKEND", "mock").lower()


@_guard
def get_order(order_id: str, user_id: Optional[str] = None) -> Optional[dict]:
    return _backend().get_order(order_id, user_id)


@_guard
def add_ticket(subject: str, detail: str, priority: str = "normal",
               escalated: bool = False, order_id: Optional[str] = None,
               user_id: Optional[str] = None) -> dict:
    return _backend().add_ticket(subject=subject, detail=detail, priority=priority,
                                 escalated=escalated, order_id=order_id,
                                 user_id=user_id)


@_guard
def seed_demo_orders(user_id: str) -> list[dict]:
    return _backend().seed_demo_orders(user_id)


@_guard
def list_tickets() -> list[dict]:
    return _backend().list_tickets()


@_guard
def search_kb(query: str) -> list[dict]:
    return _backend().search_kb(query)


@_guard
def get_session(session_id: str) -> list[dict]:
    return _backend().get_session(session_id)


@_guard
def save_session(session_id: str, messages: list[dict]) -> None:
    return _backend().save_session(session_id, messages)


@_guard
def clear_session(session_id: str) -> None:
    return _backend().clear_session(session_id)


def reset_tickets() -> None:
    return _backend().reset_tickets()


def __getattr__(name: str):
    """Expose backend-specific internals (mock's TICKETS/ORDERS/KNOWLEDGE_BASE).

    Only reached when the lookup above misses, so the frozen interface always
    wins. Accessing a mock-only name while the Supabase backend is live raises
    AttributeError — by design.
    """
    if name.startswith("_") or name.endswith("_store"):
        raise AttributeError(name)      # never proxy dunders or submodule names
    return getattr(_backend(), name)
