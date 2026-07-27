"""Shared typed contracts.

These shapes are frozen for the phase. Both the HTTP surface and the tool layer
import from here so a change is visible as an architecture decision, not a quiet
drift between layers.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

# --- HTTP contract: POST /chat -----------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(default="default", min_length=1, max_length=128)


class AgentAction(BaseModel):
    """A visible trace of something the agent actually did.

    The frontend renders these as action chips, which is how the UI proves an
    agent ran rather than a canned reply being returned.
    """

    kind: str
    label: str
    ref: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    actions: list[AgentAction] = []


# --- HTTP contract: GET /health ----------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    provider: Literal["mock", "gemini"]
    store: Literal["mock", "postgres"]
    db: Literal["up", "down"]


# --- Tool contract: order_lookup ---------------------------------------------


class OrderStatus(BaseModel):
    """The scoped subset of an order the model is allowed to see.

    Deliberately excludes customer email, name and address: the identity check
    happens inside the tool, so there is no reason to spend tokens on PII or to
    risk the model repeating it back.
    """

    order_id: str
    status: str
    placed_at: str
    carrier: str | None = None
    tracking_number: str | None = None
    eta: str | None = None
    item_count: int
    total: str


class OrderLookupResult(BaseModel):
    """Every outcome is a typed value, including the failures.

    A missing order or a failed identity check is a normal result the agent
    reasons about — never an exception that becomes a 500.
    """

    outcome: Literal["found", "not_found", "identity_mismatch"]
    order: OrderStatus | None = None
    message: str

    def __str__(self) -> str:
        return _for_model(self)


# --- Tool contract: product_catalog ------------------------------------------


class ProductCard(BaseModel):
    """One product, in the shape the comparison card renders."""

    product_id: str
    name: str
    price: str
    in_stock: bool
    summary: str
    # The fields a customer actually compares on. Kept as a flat map so the
    # frontend can lay two of these side by side without knowing the category.
    attributes: dict[str, str] = {}


class ProductLookupResult(BaseModel):
    outcome: Literal["found", "no_match"]
    products: list[ProductCard] = []
    message: str

    def __str__(self) -> str:
        return _for_model(self)


# --- Tool contract: policy_retriever -----------------------------------------


class PolicyPassage(BaseModel):
    """A grounded passage. `source_ref` is what makes an answer quotable.

    Phase 4's grounding guardrail trips when this is missing, so no passage may
    ever be constructed without one.
    """

    topic: str
    text: str
    source_ref: str


class PolicyLookupResult(BaseModel):
    outcome: Literal["found", "no_match"]
    passages: list[PolicyPassage] = []
    message: str

    def __str__(self) -> str:
        return _for_model(self)


# --- Tool contract: refund_processor -----------------------------------------


class RefundResult(BaseModel):
    outcome: Literal["executed", "refused", "already_refunded"]
    refund_id: str | None = None
    amount: str | None = None
    message: str

    def __str__(self) -> str:
        return _for_model(self)


# --- Tool contract: human_escalation ------------------------------------------


class EscalationResult(BaseModel):
    outcome: Literal["escalated"]
    escalation_id: str
    message: str

    def __str__(self) -> str:
        return _for_model(self)


# --- Tool contract: send_summary_email ----------------------------------------


class EmailResult(BaseModel):
    outcome: Literal["sent", "already_sent", "refused", "failed"]
    # Deliberately no recipient address. The agent does not choose who is emailed
    # and has no reason to see the address, so it never enters the transcript.
    message: str

    def __str__(self) -> str:
        return _for_model(self)


# --- HTTP contract: feedback ---------------------------------------------------


class FeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    recorded: bool
    rating: int
    message: str


class FeedbackSummary(BaseModel):
    responses: int
    average_rating: float | None
    ratings: dict[str, int]


# --- HTTP contract: accounts --------------------------------------------------
#
# Sign-up is for sellers. An end customer is identified by order id + email
# because the widget lives on the seller's own site, so they have no account
# here to have.


class SignupRequest(BaseModel):
    business_name: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    # Length is the control that actually matters; composition rules push people
    # toward "Password1!" and no further.
    password: str = Field(min_length=10, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class AccountView(BaseModel):
    user_id: str
    business_id: str
    business_name: str
    email: str
    name: str
    role: str


class AuthResponse(BaseModel):
    token: str
    expires_in_days: int
    account: AccountView


# --- HTTP contract: onboarding -------------------------------------------------


class PolicyDraft(BaseModel):
    topic: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=8000)


class OnboardingContext(BaseModel):
    """The seller's context feed (SPEC §12).

    Policies arrive as text the seller wrote, and become the passages their agent
    is allowed to cite. Nothing else is accepted here: what the agent may say is
    exactly what the seller supplied.
    """

    policies: list[PolicyDraft] = Field(min_length=1, max_length=40)


class OnboardingResult(BaseModel):
    passages: int
    source_refs: list[str]
    message: str


# --- HTTP contract: integrations ----------------------------------------------


class IntegrationRequestBody(BaseModel):
    contact_name: str = Field(min_length=1, max_length=120)
    contact_email: str = Field(min_length=3, max_length=254)
    website: str = Field(default="", max_length=300)
    platform: str = Field(default="", max_length=80)
    monthly_conversations: str = Field(default="", max_length=40)
    notes: str = Field(default="", max_length=2000)


class IntegrationRequestView(BaseModel):
    request_id: str
    contact_name: str
    contact_email: str
    website: str
    platform: str
    monthly_conversations: str
    notes: str
    status: str
    created_at: str


class IntegrationRequestList(BaseModel):
    requests: list[IntegrationRequestView]


class IntegrationAccepted(BaseModel):
    request_id: str
    status: str
    message: str


# --- HTTP contract: analytics -------------------------------------------------


class Analytics(BaseModel):
    """The success signals from SPEC §16.5, computed from real records.

    Every rate is `None` rather than 0 when there is nothing to divide by. A
    deflection rate of "100%" from zero conversations is not a good number, it is
    an absent one, and a dashboard that cannot tell the difference will be
    believed at the wrong moment.
    """

    conversations: int
    escalated_conversations: int
    # Share of conversations resolved without needing a person.
    deflection_rate: float | None
    escalations: dict[str, int]
    # Share of settled Decision Cards the operator approved as prepared.
    handoff_approval_rate: float | None
    csat_responses: int
    csat_average: float | None
    refunds_executed: int
    model_requests: int
    total_tokens: int
    tokens_per_conversation: float | None
    cost_per_conversation: float | None
    # Why a cost is missing, when it is.
    cost_note: str | None = None


# --- HTTP contract: the operations overview -----------------------------------
#
# The seller's own view of their store. Operator-only, and never reachable by a
# tool — so unlike everything the model sees, these are not scoped for token
# cost. They are still scoped for PII: customer email is omitted, because the
# operator screens that exist today have no use for it.


class OrderSummary(BaseModel):
    order_id: str
    customer_name: str
    status: str
    placed_at: str
    eta: str | None = None
    item_count: int
    total: str


class ProductSummary(BaseModel):
    product_id: str
    name: str
    price: str
    stock: int
    in_stock: bool
    summary: str


class PolicySummary(BaseModel):
    doc: str
    topic: str
    source_ref: str


class ActivityEntry(BaseModel):
    actor: str
    action: str
    target: str
    outcome: str
    ts: str


class OverviewResponse(BaseModel):
    orders: list[OrderSummary]
    products: list[ProductSummary]
    policies: list[PolicySummary]
    recent_activity: list[ActivityEntry]
    counts: dict[str, int]


class EmailPreview(BaseModel):
    """A summary email as it was actually rendered and stored.

    Serves the demo's "here is what the customer receives" step with the real
    message rather than a mock-up of one.
    """

    subject: str
    body_html: str
    recipient: str
    status: str
    feedback_token: str


# --- HTTP contract: the operator queue ----------------------------------------


class DecisionCard(BaseModel):
    """What an operator reads to decide in seconds.

    Everything here was produced by a tool during the run, never by the model
    asserting it — that is what makes it safe to act on with one click.
    """

    escalation_id: str
    status: Literal["pending", "approved", "declined"]
    created_at: str
    customer: dict[str, Any] = {}
    request: str = ""
    policy_check: dict[str, Any] = {}
    proposed_action: dict[str, Any] = {}
    options: list[str] = ["approve", "decline"]
    resolved_by: str | None = None
    resolution_reason: str | None = None


class EscalationList(BaseModel):
    escalations: list[DecisionCard]


class DecisionRequest(BaseModel):
    decision: Literal["approve", "decline"]
    reason: str | None = Field(default=None, max_length=500)


class DecisionResponse(BaseModel):
    escalation_id: str
    status: Literal["approved", "declined"]
    outcome: str
    customer_reply: str | None = None


def _for_model(result: BaseModel) -> str:
    """What the *model* sees for a tool result.

    The Agents SDK stringifies a tool's return value before handing it back to
    the model, and the default for a Pydantic model is Python repr
    (`outcome='found' order=OrderStatus(...)`). That is both wasteful in tokens
    and awkward to parse reliably. Emitting compact JSON instead keeps the result
    unambiguous for the model while `ToolCallOutputItem.output` stays a typed
    object for our own code.
    """
    return result.model_dump_json(exclude_none=True)
