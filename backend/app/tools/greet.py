"""The greeting tool.

There was no home for "hi". The Orchestrator is pinned to `tool_choice="required"`
so it cannot answer anything itself, and its only tools were handoffs — so a
greeting was forced into a specialist, Support ran retrieval on the word "hi",
retrieval correctly found nothing, and the customer was told their question
wasn't covered by the store's documents. Every part of that worked as designed;
the design was missing a case.

Two things this deliberately does *not* do:

- It does not let the Orchestrator improvise. The words come from here, so the
  first sentence a customer reads always sets the right expectation of what the
  thing can do, and never promises a capability that does not exist.
- It does not become a general chat escape hatch. It answers a greeting and
  names the four jobs; anything with actual content still routes.
"""

from __future__ import annotations

from agents import RunContextWrapper, function_tool

from app.core import audit
from app.core.auth import TenantContext
from app.core.config import get_settings
from app.schemas import GreetResult

# What it can actually do, in the customer's words rather than the tool's. Kept
# in step with `TOOLS` in the frontend's lib/tools.ts by hand — there are only
# four of them, and generating this from the agent graph would tie the opening
# line of every conversation to a refactor.
CAN_DO = [
    "track an order once you've confirmed it's yours",
    "answer questions about delivery, returns and warranty from the store's own policies",
    "compare products and check what's in stock",
    "start a refund, within the store's rules",
]


@function_tool
async def greet(ctx: RunContextWrapper[TenantContext]) -> GreetResult:
    """Open the conversation.

    Use this — and only this — when the customer has said hello, thanked you,
    said goodbye, or asked what you can do, and their message contains no actual
    request. Anything with a question or a task in it goes to a specialist
    instead, even if it also says hello.

    Reply using the message this returns. Do not add capabilities to it.
    """
    tenant = ctx.context
    tenant.note_tool("greet")

    name = await tenant.store.get_business_name(tenant.business_id)
    business = name or get_settings().business_display_name

    await audit.record(tenant, action="greet", target=business, outcome="greeted")

    return GreetResult(
        outcome="greeted",
        business_name=business,
        can_do=CAN_DO,
        message=(
            f"Hello — I'm the support assistant for {business}. "
            "I can track an order, explain the store's delivery and returns "
            "policies, compare products, and start a refund. What can I help "
            "you with?"
        ),
    )
