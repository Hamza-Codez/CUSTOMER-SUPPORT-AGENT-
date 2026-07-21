# PRD — Customer Support Agent (Digital FTE)

**Owner:** [You] · **Date:** July 2026 · **Status:** Draft v2 (skill-aligned)
**Replaces:** Tier-1 Customer Support Executive

> Every scope area below maps to exactly one owning skill and one phase, so
> spec-driven and skill-driven build stay in lockstep.

---

## Problem
Tier-1 support is repetitive, slow, and rule-bound: customers wait for answers to
FAQs, order status, and refunds that follow fixed policy. Humans spend most of
their time on low-complexity tickets instead of the cases that need judgment.

## Goal
Ship a web-based AI agent that resolves the majority of Tier-1 tickets end-to-end
(answer, act, log), cleanly hands off the rest to a human, and does it behind
real auth with a real datastore.

## Success Metrics
- **≥70%** of Tier-1 messages resolved without a human.
- **<10s** median response time.
- **100%** of actions (refunds, tickets, escalations) logged and auditable.
- **0** refunds issued outside policy (hard rule).
- **≥95%** correct escalation of out-of-policy / complex cases.
- **100%** of state-changing endpoints require a valid session.

## Users
- **Customer:** instant, accurate answers and actions.
- **Human agent:** receives only judgment-needed escalations, with full context.

---

## Scope — by concern, skill, and phase
Each row is owned by one skill and lands in one phase. Nothing is built outside a row.

| # | Scope area | In scope (v1) | Owning skill | Phase |
|---|---|---|---|---|
| 1 | **System architecture** | End-to-end blueprint, frozen contracts, data-flow map, failure paths, phasing | `fte-system-architecture` | 1 |
| 2 | **Agent + guardrails** | ReAct loop; 5 tools; policy-in-code (refunds); grounded answers; human handoff | `agent-handoffs-guardrails` | 1 |
| 3 | **Backend** | FastAPI layered app; `/health`, `/chat`, `/tickets`; session memory; validation + error handling | `fastapi-backend-architecture` | 1 |
| 4 | **Frontend** | Next.js + Tailwind + shadcn; chat + ticket dashboard; loading/empty/error states; action chips | `frontend-tailwind-shadcn` | 1→3 |
| 5 | **Data + DB** | Store interface; Supabase (Postgres); pgvector RAG for KB; mock→real swap | `data-flow-and-database` | 2 |
| 6 | **Auth + onboarding** | Supabase Auth; protected routes; customer vs agent roles; first-run onboarding | `auth-and-onboarding` | 4 |
| 7 | **Stories + acceptance** | Every feature as a user story with testable given/when/then + end-to-end DoD | `user-stories-and-acceptance` | all |

## Phases (each ends in a working, demoable slice)
1. **Agent + tools + backend + minimal UI on mock store** — works end to end, zero setup. *(done: scaffold)*
2. **Real data** — Supabase + pgvector behind the same store contracts.
3. **Streaming + polished UI** — Tailwind/shadcn, non-generic, full states.
4. **Auth + onboarding** — Supabase Auth, protected routes, guided first run.
5. **Deploy** — Vercel (frontend) + Render (backend).

---

## Non-Goals (v1)
- Multi-language support.
- Voice/phone channel — web chat only.
- Live payment execution — refund tool is stubbed until a payments API is chosen.
- Account self-service beyond auth (address/password management).
- Proactive outreach — inbound only.

*(Auth, database, and onboarding are NOT non-goals — they are scoped rows 5–6,
scheduled in phases 2 and 4.)*

---

## Solution Flow (end-to-end)
```
Customer (authed) → chat → Agent reasons → picks a tool
   ├─ search_kb        → grounded answer (pgvector RAG)
   ├─ track_order      → order status
   ├─ process_refund   → refund IF refundable, else escalate
   ├─ create_ticket    → log follow-up
   └─ escalate_to_human→ high-priority ticket + handoff
All actions → tickets table → live dashboard (agent role only)
```

## Least-Error Guardrails
- Refund policy enforced in code, not prompt (`agent-handoffs-guardrails`).
- Agent never invents facts; KB miss → escalate (`agent-handoffs-guardrails`).
- Every action writes an auditable ticket (`fastapi-backend-architecture` + `data-flow-and-database`).
- Real integrations swap behind frozen contracts — no rewrites (`fte-system-architecture`).
- Mock provider runs the full flow with zero external deps for CI (all phases).
- Every feature closes only via the end-to-end DoD (`user-stories-and-acceptance`).

## Definition of Done (per feature)
input → action → persisted → visible in UI · failure path handled · action logged ·
tested on mock provider · owning skill applied and named · no scope beyond this PRD.

## Open Decisions (close before their phase)
- **Model** (phase 1 swap): OpenAI (quality) vs Ollama (zero cost).
- **Payments API** (unblocks real refunds): which provider replaces the stub.
- **KB source docs** (phase 2): which documents seed pgvector.