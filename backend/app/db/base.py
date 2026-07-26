"""The data-layer contract.

Both the in-memory and the Postgres store implement this exact interface, so the
tool layer above cannot tell them apart. Swapping one for the other is a config
change, never a code change.

`business_id` is the first argument of every data method on purpose: tenancy is
not something a caller can forget to apply.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class OrderRecord:
    """A full order row as the data layer knows it.

    This includes `customer_email`, which the tool needs to verify identity and
    which must never reach the model. The tool narrows this to `OrderStatus`.
    """

    order_id: str
    business_id: str
    customer_email: str
    customer_name: str
    status: str
    placed_at: str
    carrier: str | None
    tracking_number: str | None
    eta: str | None
    item_count: int
    total: str


@dataclass
class AuditEntry:
    business_id: str
    actor: str
    action: str
    target: str
    outcome: str
    detail: dict[str, Any] = field(default_factory=dict)
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Store(ABC):
    """The only interface the tool layer is allowed to talk to."""

    kind: str

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def health(self) -> bool:
        """True if the backing data store is reachable right now."""

    # --- records --------------------------------------------------------------

    @abstractmethod
    async def get_order(self, business_id: str, order_id: str) -> OrderRecord | None:
        """Fetch one order scoped to a tenant. Returns None if it does not exist
        for that tenant — a caller can never reach another business's row."""

    # --- audit ----------------------------------------------------------------

    @abstractmethod
    async def write_audit(self, entry: AuditEntry) -> None: ...

    @abstractmethod
    async def recent_audit(self, business_id: str, limit: int = 20) -> list[AuditEntry]:
        """Newest first. Used by tests and, later, the operations dashboard."""

    # --- agent session memory -------------------------------------------------
    # Backs our SessionABC implementation. The SDK's SQLiteSession does not exist
    # in openai-agents 0.18.3, so conversation memory is our responsibility.

    @abstractmethod
    async def get_session_items(
        self, business_id: str, session_id: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Oldest first. `limit` returns the most recent N, still oldest first."""

    @abstractmethod
    async def add_session_items(
        self, business_id: str, session_id: str, items: list[dict[str, Any]]
    ) -> None: ...

    @abstractmethod
    async def pop_session_item(
        self, business_id: str, session_id: str
    ) -> dict[str, Any] | None:
        """Remove and return the newest item, or None if the session is empty."""

    @abstractmethod
    async def clear_session(self, business_id: str, session_id: str) -> None: ...
