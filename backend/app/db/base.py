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


@dataclass(frozen=True)
class ProductRecord:
    product_id: str
    business_id: str
    name: str
    price: str
    stock: int
    summary: str
    attributes: dict[str, str]

    @property
    def in_stock(self) -> bool:
        return self.stock > 0


@dataclass(frozen=True)
class PolicyRecord:
    """A parsed passage of the seller's own written policy.

    `source_ref` is mandatory, not decorative: an answer that cannot cite one is
    an answer the agent is not allowed to give.
    """

    business_id: str
    topic: str
    text: str
    source_ref: str


@dataclass(frozen=True)
class RefundRecord:
    refund_id: str
    business_id: str
    order_id: str
    amount: str
    reason: str
    status: str  # "executed" | "declined"
    approved_by: str | None = None


@dataclass
class EscalationRecord:
    """A Decision Card plus everything needed to resume the paused run.

    `run_state` is the serialised `RunState`. It is what makes the human-approval
    loop work across requests: the run pauses now, an operator decides minutes or
    hours later in a different process, and execution continues from exactly where
    it stopped rather than being re-improvised.
    """

    escalation_id: str
    business_id: str
    session_id: str
    status: str  # "pending" | "approved" | "declined"
    decision_card: dict[str, Any]
    run_state: dict[str, Any] | None = None
    resolved_by: str | None = None
    resolution_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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

    # Products and policies are returned whole, per tenant, and ranked in Python
    # by `app/rag/keyword.py`. Both sets are small and slow-changing, and doing
    # the matching in one place is what guarantees the mock and Postgres stores
    # rank identically. Phase 4 replaces the ranking with a vector search; these
    # signatures are the seam it swaps behind.

    @abstractmethod
    async def list_products(self, business_id: str) -> list[ProductRecord]: ...

    @abstractmethod
    async def list_policies(self, business_id: str) -> list[PolicyRecord]: ...

    # --- money and escalations -------------------------------------------------

    @abstractmethod
    async def create_refund(self, record: RefundRecord) -> bool:
        """Record a refund. Returns False if this order already has one.

        One refund per order is enforced by the data layer, not by the agent
        remembering. A retried run, a duplicated request or a second approval
        cannot pay the same order twice.
        """

    @abstractmethod
    async def get_refund(self, business_id: str, order_id: str) -> RefundRecord | None: ...

    @abstractmethod
    async def create_escalation(self, record: EscalationRecord) -> None: ...

    @abstractmethod
    async def list_escalations(
        self, business_id: str, status: str | None = None, limit: int = 50
    ) -> list[EscalationRecord]:
        """Newest first — the operator queue."""

    @abstractmethod
    async def get_escalation(
        self, business_id: str, escalation_id: str
    ) -> EscalationRecord | None: ...

    @abstractmethod
    async def resolve_escalation(
        self,
        business_id: str,
        escalation_id: str,
        status: str,
        resolved_by: str,
        reason: str | None = None,
    ) -> bool:
        """Settle a pending card. Returns False if it was already resolved —
        which is what stops two operators approving the same refund."""

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
