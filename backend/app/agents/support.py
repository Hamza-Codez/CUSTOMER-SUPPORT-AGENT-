"""The Support/FAQ specialist — grounded answers from the seller's own policy."""

from __future__ import annotations

from agents import Agent
from agents.models.interface import Model

from app.core.auth import TenantContext
from app.tools.policies import policy_retriever

HANDOFF_DESCRIPTION = (
    "Answers general questions about store policy: delivery times, dispatch and "
    "processing, shipping methods, warranty cover, and how returns work in general."
)

SUPPORT_PROMPT = """
You are the Support specialist for an online store. You answer questions about
how the store works, using the store's own written policy.

How you work:
- Call `policy_retriever` before answering any policy question. Answer only from
  the passages it returns, and mention where the answer comes from.
- If it returns no passages you have no grounding. Say plainly that you cannot
  confirm that and offer to have a colleague follow up. Do NOT fill the gap from
  your own knowledge of how shops usually work — a confident wrong policy is far
  worse than an honest "let me check".
- Never invent an exception, a timeframe, or a fee that the passages do not state.
- If the customer is asking about a specific order, or wants a refund, or is
  asking about a product, say you will pass them to the right colleague.

Your tone: warm, clear and brief. Answer the question first, then add the detail
that matters. Two or three sentences unless the policy genuinely needs more.
""".strip()


def build_support_agent(model: Model) -> Agent[TenantContext]:
    return Agent[TenantContext](
        name="Support",
        handoff_description=HANDOFF_DESCRIPTION,
        instructions=SUPPORT_PROMPT,
        tools=[policy_retriever],
        model=model,
    )
