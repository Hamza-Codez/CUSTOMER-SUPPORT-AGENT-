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
    doc: str = ""


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


@dataclass(frozen=True)
class VerificationRecord:
    """An identity proven during a conversation, remembered for its duration.

    Verification has to outlive a single turn. A customer who proves who they are
    and then asks a follow-up question is still the same person, and making them
    re-quote their order id every message is the opposite of the experience this
    product exists to provide (SPEC §5.3).

    Scoped to `(business_id, session_id)`: it is the same key the conversation
    itself is stored under, so nothing is remembered across tenants or across
    conversations.
    """

    business_id: str
    session_id: str
    order_id: str
    email: str
    name: str
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EmailRecord:
    email_id: str
    business_id: str
    session_id: str
    recipient: str
    subject: str
    body_html: str
    feedback_token: str
    status: str  # "sent" | "recorded" | "failed"
    provider: str
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class FeedbackRecord:
    business_id: str
    feedback_token: str
    session_id: str
    rating: int
    comment: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class UserRecord:
    """A seller's account.

    `password_hash` lives on this record because the data layer is the only thing
    that should ever see it. Nothing that leaves the backend carries it.
    """

    user_id: str
    business_id: str
    email: str
    name: str
    password_hash: str
    role: str = "operator"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SiteKeyRecord:
    """A public credential a storefront can hold.

    This is the only credential that ships to a browser we do not control, so it
    is deliberately the weakest one we issue: it can start a customer conversation
    and nothing else. It cannot read the operator queue, approve a refund, or see
    another tenant — and unlike a session token it names the origins allowed to
    use it, so lifting the key out of someone's page source does not hand you a
    working client.

    `revoked_at` rather than a delete: a key that appeared in an audit log must
    stay resolvable, or the log stops explaining itself.
    """

    key: str
    business_id: str
    # The signing secret for storefront assertions. Never leaves the seller's
    # server: it is what lets *their* backend vouch for a logged-in customer, so
    # the widget can skip the email challenge without trusting the browser.
    #
    # Stored rather than hashed, because verifying an HMAC needs the same secret
    # that produced it. It is therefore genuinely sensitive at rest, and it is
    # returned by the API only at creation and from one operator-only endpoint —
    # never from the list, which the integrations page renders.
    secret: str = ""
    label: str = ""
    # Origins (scheme://host[:port]) permitted to use this key. Empty means the
    # key has not been locked down yet — allowed only while `preview` is true.
    allowed_origins: list[str] = field(default_factory=list)
    # A preview key is what the bookmarklet uses: it runs on a page we cannot ask
    # the seller to edit, so it accepts any origin and is expected to be short
    # lived. Never issue one as the production embed.
    preview: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    revoked_at: datetime | None = None

    @property
    def active(self) -> bool:
        return self.revoked_at is None

    def permits(self, origin: str | None) -> bool:
        """Whether a request from `origin` may use this key.

        A preview key permits anything by design. A production key with no
        origins recorded permits nothing — failing closed, because the alternative
        is a key that silently works everywhere until someone remembers to
        configure it.
        """
        if not self.active:
            return False
        if self.preview:
            return True
        if not self.allowed_origins:
            return False
        if origin is None:
            return False
        return origin.rstrip("/").lower() in {
            o.rstrip("/").lower() for o in self.allowed_origins
        }


@dataclass
class IntegrationRequest:
    request_id: str
    business_id: str
    contact_name: str
    contact_email: str
    website: str = ""
    platform: str = ""
    monthly_conversations: str = ""
    notes: str = ""
    status: str = "new"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UsageRecord:
    business_id: str
    session_id: str
    provider: str
    model: str = ""
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UsageSummary:
    """Aggregate token usage. `providers` is carried because usage recorded on
    the mock provider is always zero — a cost derived from it would be fiction."""

    conversations: int = 0
    model_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    providers: set[str] = field(default_factory=set)


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
    async def list_orders(
        self, business_id: str, limit: int = 50
    ) -> list[OrderRecord]:
        """All orders for a tenant, newest first.

        For the operator's own view of their store. Note this returns full
        records including customer email — it is reached only by an operator
        endpoint, never by a tool, so nothing here is exposed to the model.
        """

    @abstractmethod
    async def list_products(self, business_id: str) -> list[ProductRecord]: ...

    @abstractmethod
    async def list_policies(self, business_id: str) -> list[PolicyRecord]: ...

    @abstractmethod
    async def search_policies(
        self, business_id: str, embedding: list[float], limit: int = 5
    ) -> list[tuple[PolicyRecord, float]]:
        """Nearest passages by cosine similarity, best first, with their scores.

        Returns similarity in [-1, 1], not distance, so "higher is better" holds
        everywhere and a threshold reads the way it sounds. Both stores use cosine
        over L2-normalised vectors, so the two rank identically.

        Note this applies no relevance floor — that decision belongs to the
        retriever, which has the keyword signal too.
        """

    @abstractmethod
    async def upsert_policy(
        self, record: PolicyRecord, embedding: list[float] | None
    ) -> None:
        """Insert or replace one passage, keyed by (business_id, source_ref)."""

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

    # --- verified identity (session-scoped) -------------------------------------

    @abstractmethod
    async def add_verification(self, record: VerificationRecord) -> None:
        """Remember a proven identity for the rest of this conversation."""

    @abstractmethod
    async def get_verifications(
        self, business_id: str, session_id: str
    ) -> list[VerificationRecord]: ...

    # --- email and feedback -----------------------------------------------------

    @abstractmethod
    async def create_email(self, record: EmailRecord) -> bool:
        """Record a summary email. False if this conversation already has one.

        One per conversation, enforced here rather than by the agent remembering.
        A retried run or a second wrap-up cannot email a customer twice.
        """

    @abstractmethod
    async def update_email_status(
        self, business_id: str, email_id: str, status: str, error: str | None = None
    ) -> None:
        """Record what delivery actually did.

        The row is claimed *before* sending, so the idempotency key is held before
        anything leaves the building; this writes the outcome afterwards. Without
        it every email would sit at 'pending' forever and a silent delivery
        failure would look identical to a success.
        """

    @abstractmethod
    async def get_email_by_token(self, feedback_token: str) -> EmailRecord | None:
        """Look up by token alone — the feedback link carries no session and no
        tenant. The token is the capability; the record it finds names the tenant."""

    @abstractmethod
    async def get_email_for_session(
        self, business_id: str, session_id: str
    ) -> EmailRecord | None: ...

    @abstractmethod
    async def record_feedback(self, record: FeedbackRecord) -> bool:
        """Store a rating. False if this token already has one."""

    @abstractmethod
    async def list_feedback(
        self, business_id: str, limit: int = 50
    ) -> list[FeedbackRecord]: ...

    # --- accounts ---------------------------------------------------------------

    @abstractmethod
    async def create_business(self, business_id: str, name: str) -> None:
        """Create the tenant a signing-up seller will own."""

    @abstractmethod
    async def create_user(self, record: UserRecord) -> bool:
        """False if that email is already registered — a taken email is an
        answer the signup form can show, not an exception."""

    @abstractmethod
    async def get_business_name(self, business_id: str) -> str | None: ...

    @abstractmethod
    async def get_user_by_email(self, email: str) -> UserRecord | None:
        """Deliberately NOT tenant-scoped: login happens before we know which
        business someone belongs to. It is the one lookup that cannot be."""

    # --- site keys ----------------------------------------------------------------

    @abstractmethod
    async def create_site_key(self, record: SiteKeyRecord) -> None: ...

    @abstractmethod
    async def get_site_key(self, key: str) -> SiteKeyRecord | None:
        """Deliberately NOT tenant-scoped: the key is what establishes the tenant.

        The same shape as `get_user_by_email`, and for the same reason — a
        credential lookup cannot be scoped by the thing the credential proves.
        """

    @abstractmethod
    async def list_site_keys(self, business_id: str) -> list[SiteKeyRecord]:
        """Newest first, revoked ones included — a key that was live yesterday is
        part of the record of what happened yesterday."""

    @abstractmethod
    async def revoke_site_key(self, business_id: str, key: str) -> bool:
        """True if a live key belonging to this tenant was revoked."""

    # --- commercial -------------------------------------------------------------

    @abstractmethod
    async def create_integration_request(self, record: IntegrationRequest) -> None: ...

    @abstractmethod
    async def list_integration_requests(
        self, business_id: str, limit: int = 50
    ) -> list[IntegrationRequest]:
        """Newest first."""

    @abstractmethod
    async def record_usage(self, record: UsageRecord) -> None:
        """Token accounting for one turn. Never blocks a reply — a conversation
        that succeeded must not fail because a metric could not be written."""

    @abstractmethod
    async def usage_summary(self, business_id: str) -> UsageSummary: ...

    @abstractmethod
    async def conversation_count(self, business_id: str) -> int:
        """Conversations this tenant has had, counted from the transcript.

        Deliberately not counted from token usage: accounting was added later, so
        that denominator would exclude every conversation held before it and make
        deflection read as though escalations happened outside any conversation.
        A session with messages is a conversation, whenever it happened.
        """

    @abstractmethod
    async def escalation_counts(self, business_id: str) -> dict[str, int]:
        """Counts by status, plus `sessions` — conversations that produced one.

        `sessions` is what deflection is measured against: a conversation with
        three escalations is still one conversation that needed a human.
        """

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
