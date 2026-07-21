# INTENT.md — Customer Support Agent (Digital FTE)

> The guiding document. If a decision isn't clearly answered by the PRD, it's
> answered here. Everything we build must trace back to this intent.

---

## 1. Why we're building this
Tier-1 support is high-volume, repetitive, and rule-bound — the exact profile a
capable agent should own. The intent is not "a chatbot." The intent is a
**digital full-time employee** that holds a defined role, uses real tools, keeps
an auditable record of its work, and knows when to hand off to a human.

Success = a customer can't tell whether a human or the agent resolved their
Tier-1 request, and a human agent only ever sees the tickets that truly need
judgment.

## 2. What "Digital FTE" means here
It qualifies as an FTE — not a tool — because it has all four:
1. **A role** — Tier-1 Customer Support, with a fixed job description.
2. **Tools** — it takes real actions (track, refund, ticket, escalate), not just talk.
3. **Memory** — it remembers the conversation within a session.
4. **Accountability** — every action produces an auditable ticket, and it escalates when unsure.

If any of these four is missing, we've built a chatbot, not an FTE.

## 3. Core behaviours (non-negotiable)
- **Grounded, never invented.** If the knowledge base has no answer, it says so and escalates. No hallucinated policy.
- **Policy enforced in code, not prompt.** Refund eligibility is a hard code check. The model cannot talk its way past it.
- **Auditable by default.** Every refund, ticket, and escalation is logged. Nothing happens silently.
- **Escalate on doubt.** Complex, sensitive, angry, or out-of-policy → human, with full context attached.
- **Concise and professional.** Friendly, short, no filler.

## 4. Scope of intent
**We are building:** a web-based agent that resolves the majority of inbound
Tier-1 chat tickets end-to-end and cleanly escalates the rest.

**We are deliberately NOT building (v1):** multi-language, voice/phone, live
payment execution, account self-service (address/password), or proactive
outreach. These are out of scope so the core stays sharp — not because they're
unimportant.

## 5. Definition of "done" (v1)
The system is done when, unaided:
- It answers a KB-backed question correctly.
- It tracks a real order by ID.
- It refunds an in-policy order and refuses an out-of-policy one.
- It escalates a complex/angry case as a high-priority ticket.
- Every action appears on the live dashboard.
- It runs end-to-end with **zero external setup** (mock provider) and swaps to a
  real model/DB by config only.

## 6. Architecture intent
```
Next.js (chat + ticket dashboard)
      │  HTTP
FastAPI (orchestration, memory, logging)
      │
LangGraph ReAct agent  ──►  tools:
      │                      search_kb · track_order · process_refund
      │                      create_ticket · escalate_to_human
      │
Model provider switch: mock (default) → OpenAI → Ollama
      │
Data: mock in-memory store now → Supabase + pgvector later
```
**Intent behind each choice:**
- *LangGraph* — explicit, inspectable agent workflow (not a black box).
- *Tools over prompting* — actions live in code so they're testable and safe.
- *Provider switch* — never blocked on an API key; test on mock, ship on real.
- *Mock-first store* — full flow works day one; production is a swap, not a rewrite.

## 7. Least-error methodology (every phase)
- **Plan:** every feature traces to a PRD metric or it doesn't get built.
- **Build:** one steady path, mock-first, swap real integrations behind the same interface.
- **Test:** each tool tested in isolation, then the full flow via the mock model — no API needed for CI.
- **Design:** minimal, presentable UI (chat + dashboard) — nothing that isn't demoable.

## 8. What good looks like at demo
Type a message → the agent answers from the KB, tracks an order, processes a
valid refund, refuses an invalid one, and escalates an angry case — all landing
live on the ticket dashboard. No manual setup, no failed endpoints.

## 9. Guardrails against scope creep
Before adding anything, it must pass all three:
1. Does it serve the Tier-1 role? (else → out of scope)
2. Does it map to a PRD success metric?
3. Is it demoable and low-risk to implement?

If it fails any one, it waits.

## 10. Open decisions (must be closed before that phase)
- **Model:** OpenAI (quality) vs Ollama (zero cost).
- **Refund execution:** which payments API replaces the stub.
- **Knowledge base:** which source documents seed the KB.