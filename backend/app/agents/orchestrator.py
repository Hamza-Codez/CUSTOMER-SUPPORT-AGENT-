"""The Orchestrator — triage and routing, and the app's single entry point.

The whole team is constructed here in one place so there is exactly one cache to
reset and one wiring diagram to read.

**On handing back:** specialists do not hand back to the Orchestrator. Every user
message starts a fresh run at the entry agent with the full session history, so
routing is re-decided each turn anyway. Adding a return path would buy nothing and
risks two agents volleying a conversation between them inside a single turn.

The one intra-turn handoff that earns its place is Orders -> Refunds: a customer
checking on an order and then asking for their money back is one continuous
thought, and making them wait a turn for it would be artificial.
"""

from __future__ import annotations

from functools import lru_cache

from agents import Agent, ModelSettings

from app.agents.orders import build_orders_agent
from app.agents.products import build_products_agent
from app.agents.refunds import build_refunds_agent
from app.agents.support import build_support_agent
from app.core.auth import TenantContext
from app.core.model import gemini_model
from app.guardrails.grounding import must_be_grounded
from app.guardrails.input_guards import scope_and_safety
from app.tools.greet import greet

TRIAGE_PROMPT = """
You are the triage coordinator for an online store's support team. You do not
answer customers yourself — you work out what they need and hand them to the
right specialist immediately.

Route on what the customer actually wants:
- An existing order: where it is, tracking, delivery status -> Orders
- A refund, a return, or wanting money back -> Refunds
- What a product is, what it costs, stock, or comparing options -> Products
- How the store works in general: delivery times, dispatch, warranty,
  how returns work as a rule -> Support

The one thing you handle yourself:
- A bare greeting, a thank you, a goodbye, or "what can you do?" -> call the
  `greet` tool and reply with what it gives you.

Rules:
- Hand off on the first message. Do not ask a clarifying question first unless
  the request is genuinely impossible to place.
- A message that says hello *and* asks for something is not a greeting. Route it.
- If a message covers two things, route to the one the customer led with.
- Never answer a policy, product or order question yourself. You do not have the
  tools to check any of it, so anything you said would be a guess.
""".strip()


@lru_cache
def get_entry_agent() -> Agent[TenantContext]:
    """The agent `/chat` starts every run with.

    Phase 1 pointed this at the Orders agent directly. Repointing it here is the
    whole of the Phase 2 change as far as the API layer is concerned — the HTTP
    contract and every tool signature are untouched.
    """
    model = gemini_model()

    refunds = build_refunds_agent(model)
    support = build_support_agent(model)
    products = build_products_agent(model)
    orders = build_orders_agent(model, handoffs=[refunds])

    return Agent[TenantContext](
        name="Orchestrator",
        instructions=TRIAGE_PROMPT,
        # The only thing triage answers itself, and it answers it from authored
        # text. See app/tools/greet.py for why a greeting needed its own tool
        # rather than being routed somewhere.
        tools=[greet],
        handoffs=[support, orders, products, refunds],
        # Handoffs reach the model as tools, so requiring a tool call makes
        # routing the only move available. The prompt above already said "never
        # answer yourself" and the live model did it anyway — twice, in different
        # runs, with different questions. Asking harder was not going to work.
        #
        # Without this the grounding guardrail still catches it, but the customer
        # gets "let me find a colleague" instead of an answer. Safe is not the
        # same as working.
        model_settings=ModelSettings(tool_choice="required"),
        # Input guardrails run on the first agent only, which is exactly here.
        input_guardrails=[scope_and_safety],
        # Backstop, not the primary defence: if a handoff somehow does not happen,
        # an ungrounded answer must still never reach the customer.
        output_guardrails=[must_be_grounded],
        model=model,
    )
