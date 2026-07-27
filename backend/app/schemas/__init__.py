"""Shared typed contracts.

These shapes are frozen for the phase. Both the HTTP surface and the tool layer
import from here so a change is visible as an architecture decision, not a quiet
drift between layers.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

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
