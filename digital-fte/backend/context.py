"""Request-scoped identity, available to the tools without changing their shape.

SPEC §5 freezes the tool signatures — `track_order(order_id: str) -> str`. The
agent decides which tool to call and knows nothing about HTTP or users, so the
caller's identity cannot travel as an argument. It travels as ambient context
instead, set once per request in `main.py` and read by the tools.

A ContextVar (not a global) because it must be isolated per request: FastAPI
serves concurrent requests, and a plain module variable would let one customer's
identity leak into another's tool call.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)


def set_user_id(user_id: Optional[str]):
    """Returns a token; pass it to `reset` to restore the previous value."""
    return _current_user_id.set(user_id)


def reset(token) -> None:
    _current_user_id.reset(token)


def current_user_id() -> Optional[str]:
    """The signed-in user, or None outside a request (unit tests, scripts).

    None means "no owner in play" — the store treats unowned demo fixtures as
    visible, but never exposes another user's owned data.
    """
    return _current_user_id.get()
