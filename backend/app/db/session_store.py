"""Conversation memory for the Agents SDK.

openai-agents 0.18.3 exposes `Session` as an abstract base only — the older
`SQLiteSession` helper is not part of this version — so persistence is ours to
implement. This adapter satisfies the SDK contract while keeping every item
scoped to a tenant, so two businesses can use the same `session_id` without ever
seeing each other's history.
"""

from __future__ import annotations

from typing import Any

from agents.memory import SessionABC

from app.db.base import Store


class StoreSession(SessionABC):
    """Session memory backed by whichever `Store` is configured."""

    def __init__(self, session_id: str, business_id: str, store: Store) -> None:
        self.session_id = session_id
        self.business_id = business_id
        self._store = store

    async def get_items(self, limit: int | None = None) -> list[Any]:
        return await self._store.get_session_items(
            self.business_id, self.session_id, limit
        )

    async def add_items(self, items: list[Any]) -> None:
        await self._store.add_session_items(
            self.business_id, self.session_id, [dict(i) for i in items]
        )

    async def pop_item(self) -> Any | None:
        return await self._store.pop_session_item(self.business_id, self.session_id)

    async def clear_session(self) -> None:
        await self._store.clear_session(self.business_id, self.session_id)
