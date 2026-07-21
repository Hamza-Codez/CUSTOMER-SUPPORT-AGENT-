"""The Digital FTE agent — a LangGraph ReAct agent (model + tools + role prompt).

`create_react_agent` builds the classic agent graph: the model reasons, decides
which tool to call, observes the result, and repeats until it can answer.
"""
from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from model import get_model
from tools import ALL_TOOLS

SYSTEM_PROMPT = """You are a Tier-1 Customer Support Agent for a furniture company.
Your job:
- Answer product, shipping, warranty, and policy questions using the search_kb tool.
- Track orders with track_order when given an order ID (format: ORD-####).
- Process refunds with process_refund ONLY when the order is refundable/within policy.
- Open tickets with create_ticket to track follow-up work.
- Escalate to a human with escalate_to_human for anything complex, sensitive,
  angry, out-of-policy, or that you are not confident about.

Rules:
- Never invent facts. Answer only from what search_kb returns.
- Never refund an order the tool says is not refundable.
- Policy is enforced by the tools themselves. When a tool reports that it has
  already escalated, relay that answer — do NOT call escalate_to_human again.
- Be concise, friendly, and professional. Relay tool results in your own words;
  never expose internal markers or raw tool output.
"""


def build_agent():
    """Construct and return the compiled agent graph."""
    model = get_model()
    return create_react_agent(model, ALL_TOOLS, prompt=SYSTEM_PROMPT)


# Singleton so the graph is built once per process.
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent
