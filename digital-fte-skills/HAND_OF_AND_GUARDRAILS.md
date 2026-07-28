---
name: agent-handoffs-guardrails
description: Build the OpenAI Agents SDK agents, their tools, agent-to-agent handoffs, human handoffs (Decision Cards), and safety guardrails for the Digital FTE Customer Support Agent so it acts reliably and never breaks policy. Use when the user asks to add or edit an agent tool, change agent behaviour, add a guardrail, define escalation/human handoff, enforce a policy (e.g. refunds), stop hallucinations, or make the agent "an FTE not a chatbot". Covers the multi-agent design, tool design, policy-in-code, the three guardrail scopes, human approval, and the reason-act loop on Gemini.
---

# Agent Handoffs & Guardrails

The agent is only trustworthy because of its guardrails. Policy lives in code and
in tool guardrails, not in the prompt. The model decides WHICH tool; the tool and
its guardrail decide WHETHER the action is allowed. Built on the **OpenAI Agents
SDK** (Agents · Tools · Handoffs · Guardrails · Sessions · Runner) driving **Gemini**.

## Non-negotiable principles
1. **Policy in code, never prompt.** Eligibility, caps, and limits are enforced by tool guardrails the model cannot talk past.
2. **Grounded or escalate.** Answers must carry a `source_ref` from the RAG store. No source → the grounding guardrail trips → escalate. No invented facts.
3. **Every action is auditable.** State-changing tools write an audit/escalation record.
4. **Escalate on doubt.** Complex, sensitive, angry, over-cap, or out-of-policy → human, with a full Decision Card.
5. **Money-moving = human-owned.** Above the auto-cap, the Runner pauses for human approval before executing.
6. **Four FTE traits present:** role, tools, memory (Session), accountability (audit). Missing one = chatbot, not FTE.

## The agent team (not one mega-agent)
| Agent | Job | Tools it may use | Hands off to |
|---|---|---|---|
| Orchestrator (triage) | route intent | *(none)* | all specialists |
| Support/FAQ | grounded answers | `policy_retriever` | Orchestrator |
| Orders | verify identity, status | `order_lookup` | Refunds, Orchestrator |
| Products | explain & compare | `product_catalog` | Orchestrator |
| Refunds | policy check + refund | `policy_retriever`, `order_lookup`, `refund_processor`, `human_escalation` | Human (approval) |

Least privilege is structural: Support literally cannot construct `refund_processor`.

## Instructions

### Step 1: Build each agent with the Agents SDK
```python
from agents import Agent, handoff
from app.core.model import gemini_model

refunds_agent = Agent(
    name="Refunds",
    instructions=REFUNDS_PROMPT,
    tools=[policy_retriever, order_lookup, refund_processor, human_escalation],
    model=gemini_model(),
)
orchestrator = Agent(
    name="Orchestrator",
    instructions=TRIAGE_PROMPT,
    handoffs=[support_agent, orders_agent, products_agent, handoff(refunds_agent)],
    model=gemini_model(),
)
```
Use **handoff** to transfer the whole conversation; use `Agent.as_tool(...)` when
one specialist needs a sub-answer without transferring (e.g. Support asks Products
for a quick comparison). The Runner performs the loop and switches agents on handoff.

### Step 2: Write each system prompt as the role's job description
Include: who it is, which tools and when to use each, and hard rules (grounded,
escalate on doubt, concise, polite). Keep it short. **The prompt guides; code and
guardrails enforce.**

### Step 3: Design each tool with a single responsibility (the frontier)
```python
from agents import function_tool
from pydantic import BaseModel

class RefundResult(BaseModel):
    status: str          # "executed" | "pending_approval" | "refused"
    ticket: str | None
    reason: str

@function_tool
async def refund_processor(order_id: str, amount: float, reason: str) -> RefundResult:
    """Prepare/execute a refund. Guardrails enforce identity, policy, and the auto-cap."""
    # code path only; the tool guardrail (Step 5) decides whether this even runs
    ...
```
Tools return typed, scoped results. The model cannot override the outcome.

### Step 4: Guardrails — use all three SDK scopes
- **Input guardrail** (before the first agent): scope check (in-domain?) + injection/abuse screen. Trip the tripwire to reject early.
- **Output guardrail** (after the final agent): **grounding** — require a `source_ref` on any policy/product claim; trip if missing → escalate instead of guessing. Plus a tone check.
- **Tool guardrail** (around every function-tool call, even inside a handoff chain): where money-moving safety lives.

```python
from agents import GuardrailFunctionOutput, output_guardrail

@output_guardrail
async def must_be_grounded(ctx, agent, output) -> GuardrailFunctionOutput:
    grounded = bool(getattr(output, "source_ref", None))
    return GuardrailFunctionOutput(output_info={"grounded": grounded},
                                   tripwire_triggered=not grounded)
```

### Step 5: The refund guardrail (policy + cap in code)
An **input tool guardrail** on `refund_processor` runs before execution and enforces:
1. identity verified (order_id + email matched earlier),
2. policy check passed (via `policy_retriever` `source_ref`),
3. `amount <= AUTO_REFUND_CAP`.

If all pass → execute + write ticket. If policy fails or amount > cap → do **not**
execute; require human approval. The Runner pauses the run, a **Decision Card** is
created, and execution resumes only after an operator approves.

### Step 6: Human handoff = the Decision Card
When escalating (over-cap, out-of-policy, angry/legal sentiment, KB miss, low
confidence), `human_escalation` (or the paused `refund_processor`) writes a
high-priority record carrying a ready-to-decide card:
```json
{
  "customer": {"name": "...", "verified": true},
  "request": "Refund — Order #10432, damaged",
  "policy_check": {"rule": "30-day damaged-goods", "result": "eligible"},
  "proposed_action": {"type": "refund", "amount": 59.0, "method": "original"},
  "options": ["approve", "adjust", "decline_with_reason"]
}
```
The operator's one click resumes the run; the outcome flows back into the same
conversation and is logged. The human starts with full context, not a cold start.

### Step 7: Ground answers
`policy_retriever` returns only real parsed KB content **with a `source_ref`**. If
empty, the grounding output guardrail trips → the agent states it can't answer and
escalates. Never let Gemini fill the gap from its own knowledge.

### Step 8: Verify guardrails hold
Must-pass cases every change:
- Refund within policy AND under cap → executed + ticket.
- Refund over cap OR out-of-policy → **not** executed → Decision Card + human approval pause.
- KB miss → grounding tripwire → no invented answer → escalated.
- Angry/legal message → escalated, high priority.
- Unverified identity → account action refused until email matches.
- Every state change → an audit/escalation record exists.

## Example
User: "This is unacceptable, refund ORD-1003 now" (ORD-1003 is out of policy).
1. Orchestrator routes to Refunds (refund intent + sentiment).
2. `refund_processor` input tool guardrail: policy check fails.
3. Tool does NOT execute; `human_escalation` writes a high-priority Decision Card with the message + order context; the run pauses.
4. Customer is told a specialist will follow up; operator sees Approve/Adjust/Decline.

## Troubleshooting
- **Agent refunded something it shouldn't:** policy was in the prompt, not the tool guardrail. Move the check into the input tool guardrail.
- **Agent invents policy/facts:** grounding output guardrail missing or `source_ref` not required. Add it; trip on empty retrieval.
- **Over-cap refund executed silently:** no auto-cap check / no approval pause. Gate `refund_processor` and require approval above `AUTO_REFUND_CAP`.
- **Handoff loses context:** by default the next agent sees history; if you filtered it, restore what the specialist needs (or thicken the Decision Card).
- **Model won't call the right tool:** tighten the tool docstring to say exactly when to use it; verify Gemini tool-calling parity early.
- **Guardrail didn't fire inside a handoff:** agent-level input/output guardrails only cover the first/last agent. Use **tool guardrails** for checks around each tool call in the chain.
