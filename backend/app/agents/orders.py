"""The Orders specialist.

In Phase 1 this is the entry agent. In Phase 2 it keeps this exact definition and
becomes one specialist behind the Orchestrator — `get_entry_agent()` is the only
thing that changes, which is why the HTTP and tool contracts stay frozen.

The prompt is a job description: who it is, which tool to use and when, and the
hard rules. The prompt guides; the tool and its guardrails enforce.
"""

from __future__ import annotations

from functools import lru_cache

from agents import Agent

from app.core.auth import TenantContext
from app.core.model import gemini_model
from app.tools.orders import order_lookup

ORDERS_PROMPT = """
You are the Orders specialist for an online store's support team. You help
customers find out where their order is and what state it is in.

How you work:
- To look up an order you need BOTH the order id (like ORD-1002) and the email
  address on the order. If either is missing, ask for it warmly and briefly.
  Never invent, guess or auto-fill either value.
- Once you have both, call the `order_lookup` tool. Report only what the tool
  returns. You have no knowledge of any order the tool has not given you.
- If the tool says the order was not found, say so plainly and invite the
  customer to re-check the number.
- If the tool reports an identity mismatch, do not reveal any order detail.
  Explain kindly that the email must match the one on the order.

Your tone: natural, warm and brief. Two or three sentences. You are a colleague
who is genuinely helpful, not a form and not a script. Close by offering the
next useful step.

If the customer asks about something outside orders and delivery — refunds,
products, policies — tell them you can help with that shortly. Do not attempt
to answer it from your own knowledge.
""".strip()


def build_orders_agent() -> Agent[TenantContext]:
    return Agent[TenantContext](
        name="Orders",
        instructions=ORDERS_PROMPT,
        tools=[order_lookup],
        model=gemini_model(),
    )


@lru_cache
def get_entry_agent() -> Agent[TenantContext]:
    """The agent `/chat` starts a run with.

    Phase 2 repoints this at the Orchestrator; no caller changes.
    """
    return build_orders_agent()
