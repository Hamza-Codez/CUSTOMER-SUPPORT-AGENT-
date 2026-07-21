---
name: agent-handoffs-guardrails
description: Build the LangGraph agent, its tools, human handoffs, and safety guardrails for the Digital FTE Customer Support Agent so it acts reliably and never breaks policy. Use when the user asks to add or edit an agent tool, change agent behaviour, add a guardrail, define escalation/human handoff, enforce a policy (e.g. refunds), stop hallucinations, or make the agent "an FTE not a chatbot". Covers tool design, policy-in-code, escalation logic, and the reason-act-observe loop.
---

# Agent Handoffs & Guardrails

The agent is only trustworthy because of its guardrails. Policy lives in code,
not in the prompt. The model decides WHICH tool; the tool decides WHETHER the
action is allowed.

## Non-negotiable principles
1. **Policy in code, never prompt.** Eligibility checks (refunds, limits) are hard code checks the model cannot talk past.
2. **Grounded or escalate.** If the knowledge base has no answer, the agent says so and hands off. No invented facts.
3. **Every action is auditable.** State-changing tools write a ticket.
4. **Escalate on doubt.** Complex, sensitive, angry, or out-of-policy -> human, with full context attached.
5. **Four FTE traits present:** role, tools, memory, accountability. Missing one = chatbot, not FTE.

## Instructions

### Step 1: Build the agent as a ReAct graph
```python
from langgraph.prebuilt import create_react_agent
agent = create_react_agent(get_model(), ALL_TOOLS, prompt=SYSTEM_PROMPT)
```
The system prompt defines the role and rules; it does NOT enforce them alone.

### Step 2: Write the system prompt as the role's job description
Include: who it is, the tools and when to use each, and hard rules (grounded,
policy, escalate on doubt, concise). Keep it short. The prompt guides; code enforces.

### Step 3: Design each tool with a single responsibility
```python
@tool
def process_refund(order_id: str, reason: str) -> str:
    order = get_order(order_id)
    if not order:
        return f"Cannot refund: no order '{order_id}'."
    if not order["refundable"]:
        return "Order NOT auto-refundable. Do not refund - escalate to a human."
    ticket = add_ticket(subject=f"Refund {order_id}", detail=reason, order_id=order_id)
    return f"Refund approved for {order_id}. Ticket {ticket['id']}."
```
The refusal branch is in code. The model cannot override `refundable`.

### Step 4: Standard tool set (the agent's authority)
| Tool | Allowed to | Writes ticket | Guardrail |
|---|---|---|---|
| search_kb | read KB | no | returns "no article" on miss |
| track_order | read order | no | not-found message on unknown id |
| process_refund | refund | yes (on success) | refuses non-refundable -> escalate |
| create_ticket | log work | yes | none |
| escalate_to_human | hand off | yes (escalated, high) | none |
A tool may only do what its row allows. New authority = new reviewed tool.

### Step 5: Human handoff (escalation)
Escalate when: KB miss, out-of-policy request, sentiment triggers (angry, legal,
manager, unacceptable), or low confidence. Escalation creates a high-priority,
`escalated=true` ticket carrying a summary + order context, so the human starts
with full context, not a cold start.

### Step 6: Ground answers
`search_kb` returns only real KB content. If empty, the agent must state it can't
answer and escalate. Never let the model fill the gap from its own knowledge.

### Step 7: Verify guardrails hold
Test these must-pass cases every change:
- Valid refund -> approved + ticket.
- Refund on non-refundable order -> refused + escalated (no refund issued).
- KB miss -> no invented answer -> escalated.
- Angry message -> escalated, high priority.
- Every state change -> a ticket exists.

## Example
User: "This is unacceptable, refund ORD-1003 now."
1. Sentiment ("unacceptable") + refund intent.
2. Guardrail: ORD-1003 is not refundable.
3. Agent does NOT refund; calls `escalate_to_human` with summary + order id.
4. High-priority escalated ticket created; customer told a specialist will follow up.

## Troubleshooting
- **Agent refunded something it shouldn't:** policy was in the prompt, not code. Move the check into the tool.
- **Agent invents policy/facts:** KB miss not forced to escalate. Make `search_kb` empty-result path trigger escalation.
- **Handoff loses context:** escalation summary too thin. Include the customer message + order id in the ticket.
- **Model won't call the right tool:** tool description unclear. Tighten the docstring to say exactly when to use it.
- **Ollama tool calls fail:** model lacks tool-calling support. Use a tool-capable model or switch provider.
