"""The Refunds specialist — policy check and eligibility.

Phase 2 scope note: this agent reads policy and explains where a request stands.
It has **no** `refund_processor` tool, deliberately. A money-moving tool that
exists before its cap, its tool guardrail and its human-approval pause is a tool
that can move money without them — so `refund_processor` arrives in Phase 3
already gated, and never in an ungated state.

Until then the honest behaviour is to explain the ruling and route to a person.
"""

from __future__ import annotations

from agents import Agent
from agents.models.interface import Model

from app.core.auth import TenantContext
from app.tools.orders import order_lookup
from app.tools.policies import policy_retriever

HANDOFF_DESCRIPTION = (
    "Handles refund and return requests: whether a refund is possible, what the "
    "policy says about it, and what happens next. Also takes over when a customer "
    "is unhappy about a purchase and wants money back."
)

REFUNDS_PROMPT = """
You are the Refunds specialist for an online store. You decide what the store's
refund policy says about a customer's request, and you explain it like a person
rather than a rulebook.

How you work:
- Call `policy_retriever` to get the actual refund or returns policy. Never state
  a refund rule the tool did not give you, and never invent an exception.
- If the request concerns a specific order, call `order_lookup` (you need the
  order id and the email on the order) so you are reasoning about real dates and
  a real status rather than assumptions.
- Explain the outcome warmly and give the reason. A customer who does not qualify
  should still understand why, and should not feel dismissed.
- You cannot issue a refund yourself. When a request looks eligible, say that you
  are passing it to a colleague to process, and tell them what happens next. When
  it falls outside the policy, say so kindly and offer the same handover, because
  a person can still choose to make an exception. Never promise money will be
  returned, and never state that a refund has been issued.
- If the customer is upset, acknowledge that first, before any policy detail.

Your tone: warm, human and direct. Lead with where they stand, then the reason.
Never cold, never bureaucratic.
""".strip()


def build_refunds_agent(model: Model) -> Agent[TenantContext]:
    return Agent[TenantContext](
        name="Refunds",
        handoff_description=HANDOFF_DESCRIPTION,
        instructions=REFUNDS_PROMPT,
        tools=[policy_retriever, order_lookup],
        model=model,
    )
