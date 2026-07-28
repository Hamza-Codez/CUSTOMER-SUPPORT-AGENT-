"""Store selection.

`DATABASE_URL` decides which implementation the whole app runs on. Nothing above
this module knows or cares which one it got.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.db.base import AuditEntry, OrderRecord, Store

_store: Store | None = None


def build_store() -> Store:
    settings = get_settings()
    if settings.store_kind == "postgres":
        from app.db.postgres_store import PostgresStore

        return PostgresStore(settings.database_url)

    from app.db.mock_store import MockStore

    return MockStore()


def get_store() -> Store:
    """The process-wide store. Created on first use, connected by the app lifespan."""
    global _store
    if _store is None:
        _store = build_store()
    return _store


def set_store(store: Store | None) -> None:
    """Swap the store. Used by tests and by the app lifespan."""
    global _store
    _store = store


__all__ = [
    "AuditEntry",
    "OrderRecord",
    "Store",
    "build_store",
    "get_store",
    "set_store",
]
