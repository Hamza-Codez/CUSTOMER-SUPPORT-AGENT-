"""The Digital FTE's tools — this is what makes it an agent, not a chatbot.

Each tool is a plain function decorated with @tool so LangGraph can call it.
Swap the bodies for real integrations (Supabase, Pinecone, a payments API)
without changing the agent graph.

Guardrail contract (policy in code, never in the prompt):
- The model decides WHICH tool runs. The tool decides WHETHER the action is allowed.
- A refusal is never left to the model to act on: the tool performs the escalation
  itself and returns customer-safe text the agent can relay verbatim.
- Tool strings are customer-facing. No operator instructions ever leak into them.
"""
from __future__ import annotations

from langchain_core.tools import tool

import context
import store


def _escalate(summary: str, order_id: str | None = None) -> dict:
    """Single path for every handoff to a human: high priority, flagged, auditable."""
    return store.add_ticket(
        subject="ESCALATION: needs human review",
        detail=summary,
        priority="high",
        escalated=True,
        order_id=order_id or None,
        user_id=context.current_user_id(),
    )


@tool
def search_kb(query: str) -> str:
    """Search the company knowledge base (FAQs, product info, policies).
    Use this to answer questions about products, shipping, warranty, or policy.
    If nothing is found this tool escalates to a human by itself — relay its
    answer and do NOT escalate again.
    """
    # Retrieval belongs to the data layer (keyword on mock, pgvector on Supabase).
    # This tool owns only the policy: format what came back, or escalate.
    docs = store.search_kb(query)

    if not docs:
        # Grounded or escalate: never let the model fill the gap from its own knowledge.
        ticket = _escalate(f"Knowledge-base miss. Customer asked: {query}")
        return (f"No knowledge-base article covers that, so I can't answer it myself. "
                f"I've passed it to a human specialist (ticket {ticket['id']}) "
                f"who will follow up shortly.")

    return "\n\n".join(f"[{d['title']}] {d['body']}" for d in docs)


@tool
def track_order(order_id: str) -> str:
    """Look up the status of an order by its ID (e.g. 'ORD-1001')."""
    order = store.get_order(order_id, context.current_user_id())
    if not order:
        # A bad ID is usually a typo, not a handoff — ask, don't escalate.
        return (f"I couldn't find an order with ID '{order_id}'. "
                f"Please double-check the ID — it looks like 'ORD-1001'.")
    parts = [
        f"Order {order['order_id']} for {order['customer']}",
        f"Items: {', '.join(order['items'])}",
        f"Total: ${order['total']:.2f}",
        f"Status: {order['status']}",
    ]
    if order["tracking"]:
        parts.append(f"Carrier: {order['carrier']} | Tracking: {order['tracking']}")
    parts.append(f"ETA: {order['eta']}")
    return " | ".join(parts)


@tool
def process_refund(order_id: str, reason: str) -> str:
    """Process a refund for an order, IF it is within policy (refundable).
    An out-of-policy order is refused and escalated by this tool itself — relay
    its answer and do NOT escalate again.
    """
    order = store.get_order(order_id, context.current_user_id())
    if not order:
        return (f"I couldn't find an order with ID '{order_id}', so I can't refund it. "
                f"Please double-check the ID — it looks like 'ORD-1001'.")

    if not order["refundable"]:
        # HARD RULE: the model cannot talk past this branch.
        ticket = _escalate(
            summary=(f"Out-of-policy refund requested for {order['order_id']} "
                     f"(status: {order['status']}, total: ${order['total']:.2f}). "
                     f"Customer's reason: {reason}. No refund issued."),
            order_id=order["order_id"],
        )
        return (f"Order {order['order_id']} isn't eligible for an automatic refund "
                f"(status: {order['status']}), so I haven't issued one. "
                f"I've escalated it to a specialist (ticket {ticket['id']}) "
                f"who will review it and follow up shortly.")

    ticket = store.add_ticket(
        subject=f"Refund issued for {order['order_id']}",
        detail=f"Refund of ${order['total']:.2f} approved. Reason: {reason}",
        priority="normal",
        order_id=order["order_id"],
        user_id=context.current_user_id(),
    )
    return (f"Refund of ${order['total']:.2f} approved for {order['order_id']}. "
            f"Logged as ticket {ticket['id']}. Funds arrive in 5-7 business days.")


@tool
def create_ticket(subject: str, detail: str, priority: str = "normal") -> str:
    """Create a support ticket to track an issue. Priority: low | normal | high."""
    ticket = store.add_ticket(subject=subject, detail=detail, priority=priority,
                              user_id=context.current_user_id())
    return f"Created ticket {ticket['id']} ({priority} priority): {subject}"


@tool
def escalate_to_human(summary: str, order_id: str = "") -> str:
    """Escalate a complex, sensitive, or out-of-policy issue to a human agent.
    Use when you are not confident or the request is outside your authority.
    """
    ticket = _escalate(summary, order_id)
    return (f"I've escalated this to a human specialist — ticket {ticket['id']} "
            f"(high priority). They'll follow up with you shortly.")


ALL_TOOLS = [search_kb, track_order, process_refund, create_ticket, escalate_to_human]
