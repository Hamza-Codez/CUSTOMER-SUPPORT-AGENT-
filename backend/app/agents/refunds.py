"""The Refunds specialist — policy check, eligibility, and the refund itself.

The agent now holds `refund_processor`, which arrived already gated: identity,
amount and duplicate checks refuse outright, and the auto-cap and refund window
pause for a human. It has never existed in an ungated form.

Note what the prompt below does *not* do: it does not state the cap, and it does
not ask the model to decide eligibility. Those live in
`app/guardrails/refund_guard.py`, where they cannot be talked around.
"""

from __future__ import annotations

from agents import Agent, ModelSettings
from agents.models.interface import Model

from app.core.auth import TenantContext
from app.guardrails.grounding import must_be_grounded
from app.tools.email import send_summary_email
from app.tools.orders import my_orders, order_lookup
from app.tools.policies import policy_retriever
from app.tools.refunds import human_escalation, refund_processor

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
- Call `my_orders` before asking the customer for anything. If they are signed
  in on the store page it gives you their real orders, and interrogating someone
  for details their own screen is already showing is how a colleague turns back
  into a form.
- If `my_orders` gives you nothing, call `order_lookup` (you need the order id
  and the email on the order) so you are reasoning about real dates and a real
  status rather than assumptions.
- If `my_orders` reports the orders as unverified, or a refund is refused because
  the order is held in the store's own system, do not argue with it: use
  `human_escalation` so a colleague can action it.
- Explain the outcome warmly and give the reason. A customer who does not qualify
  should still understand why, and should not feel dismissed.
- To issue a refund, call `refund_processor` with the order id and the order's
  full total. You do not judge whether it is allowed — that is enforced outside
  you. Read what the tool returns and say only that:
    * 'executed' means the money is on its way. Only then may you say so.
    * If the run is paused for a colleague's approval, tell the customer a
      colleague is reviewing it and will be in touch. Do not promise an outcome.
    * If the tool refuses, explain the reason it gives and what would fix it.
- Never tell a customer they have been refunded unless the tool said 'executed'.
  Being wrong about that is the worst mistake you can make.
- Use `human_escalation` when the customer is upset, asks for a person, or wants
  something the policy does not cover.
- Once a refund is settled, or if the customer asks for it in writing, call
  `send_summary_email` once. You do not choose or ask for an address — it is
  always the verified one on the order. Never read an email address aloud.
- If the customer is upset, acknowledge that first, before any policy detail.

Your tone: warm, human and direct. Lead with where they stand, then the reason.
Never cold, never bureaucratic.
""".strip()


def build_refunds_agent(model: Model) -> Agent[TenantContext]:
    return Agent[TenantContext](
        name="Refunds",
        handoff_description=HANDOFF_DESCRIPTION,
        instructions=REFUNDS_PROMPT,
        tools=[
            policy_retriever,
            my_orders,
            order_lookup,
            refund_processor,
            human_escalation,
            send_summary_email,
        ],
        # Must retrieve before it speaks. `reset_tool_choice` (Agent default True)
        # releases this after the first tool call, so it can still write the final
        # reply — this forces a lookup, not a loop. Added because the live model
        # answered from its own knowledge instead of calling its tool, which the
        # grounding guardrail caught but only by withholding the answer entirely.
        model_settings=ModelSettings(tool_choice="required"),
        output_guardrails=[must_be_grounded],
        model=model,
    )
