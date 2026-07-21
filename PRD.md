# PRD — Customer Support Agent (Digital FTE)

**Owner:** [You] · **Date:** July 2026 · **Status:** Draft v1 · **One page by design**

---

## Problem
Tier-1 support is repetitive, slow, and expensive: customers wait for answers to
FAQs, order status, and refunds that follow fixed rules. Human agents spend most
of their time on low-complexity tickets instead of the cases that actually need
judgment.

## Goal
Ship a web-based AI agent that resolves the majority of Tier-1 tickets end-to-end
(answer, act, log) and cleanly hands off everything else to a human.

## Success Metrics
- **≥70%** of incoming Tier-1 messages resolved without a human.
- **<10s** median response time.
- **100%** of actions (refunds, tickets, escalations) logged and auditable.
- **0** refunds issued outside policy (hard rule).
- **≥95%** correct escalation of out-of-policy / complex cases.

## In Scope (v1)
- Answer FAQs, product, shipping, warranty, and policy questions (grounded, no invented answers).
- Track orders by ID.
- Process refunds **within policy only**.
- Create support tickets.
- Escalate complex/sensitive/out-of-policy cases to a human.
- Per-session memory + a live ticket dashboard.

## Non-Goals (v1)
- No multi-language support.
- No live payments integration (refund tool is stubbed until an API is chosen).
- No voice/phone channel — web chat only.
- No self-service account changes (address, password).
- No proactive outreach — inbound only.

## Users
- **Customer:** gets instant, accurate answers and actions.
- **Human agent:** receives only the escalations that need judgment, with full context.

## Solution Flow (end-to-end)
```
Customer message → Agent reasons → picks a tool
   ├─ search_kb        → grounded answer
   ├─ track_order      → order status
   ├─ process_refund   → refund IF refundable, else escalate
   ├─ create_ticket    → log follow-up
   └─ escalate_to_human→ high-priority ticket + handoff
All actions → ticket log → live dashboard
```

## Stack
Next.js (chat + dashboard) · FastAPI · LangGraph agent · OpenAI **or** local Ollama ·
mock store now → Supabase + pgvector later · Vercel + Render.

## Least-Error Guardrails
- Refund tool enforces the policy check in code, not in the prompt.
- Agent never invents facts — falls back to escalation when the KB has no answer.
- Every action writes an auditable ticket.
- Mock provider lets us test the full flow with zero external dependencies.

## Milestones
1. Agent + tools on mock store (**done** — working scaffold).
2. Real KB via Supabase + pgvector.
3. Streaming chat UI.
4. Deploy (Vercel + Render).