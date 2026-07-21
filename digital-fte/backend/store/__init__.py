"""The data layer's only public seam.

Everything upstream (tools, agent, API) calls `store.<fn>` and never learns
whether the answer came from a dict or from Postgres. The backend is chosen at
call time by env var, mirroring `model.get_model()`:

    DATA_BACKEND = mock | supabase        (default: mock)

Frozen interface — both backends implement these identically:

    get_order(order_id: str) -> dict | None
    add_ticket(subject, detail, priority="normal", escalated=False,
               order_id=None) -> dict
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

import importlib
import os
from typing import Optional

_BACKENDS = {"mock": ".mock_store", "supabase": ".supabase_store"}


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


def get_order(order_id: str) -> Optional[dict]:
    return _backend().get_order(order_id)


def add_ticket(subject: str, detail: str, priority: str = "normal",
               escalated: bool = False, order_id: Optional[str] = None) -> dict:
    return _backend().add_ticket(subject=subject, detail=detail, priority=priority,
                                 escalated=escalated, order_id=order_id)


def list_tickets() -> list[dict]:
    return _backend().list_tickets()


def search_kb(query: str) -> list[dict]:
    return _backend().search_kb(query)


def get_session(session_id: str) -> list[dict]:
    return _backend().get_session(session_id)


def save_session(session_id: str, messages: list[dict]) -> None:
    return _backend().save_session(session_id, messages)


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
