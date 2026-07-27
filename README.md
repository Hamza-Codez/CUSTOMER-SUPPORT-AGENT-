# Digital FTE — Agent Platform

An AI agent e-commerce businesses **hire** to run frontline operations: customer
support, order tracking, product guidance and policy-compliant refunds — with
humans owning every decision that moves money.

Not a chatbot. It pulls real records through controlled tools, follows the
business's own written policies, handles routine work on its own, and prepares
the risky calls as a one-click decision for a person.

## The documents

| Document | What it is |
|---|---|
| [INTENT.md](INTENT.md) | Product intent and vision — the why and what |
| [SPEC.md](SPEC.md) | Technical specification — the how |
| [digital-fte-skills/](digital-fte-skills/) | The build skills this code conforms to |

## The code

| Directory | Status |
|---|---|
| [backend/](backend/) | **Phases 1–5 complete** — agent team, guardrails, gated refunds, human approval, grounded RAG, summary mailer |
| `frontend/` | Not started (Phase 6) |

Start with [backend/README.md](backend/README.md). It runs with zero setup:

```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload
```

## Stack

Next.js · FastAPI on `uv`/`uvicorn` · OpenAI Agents SDK · Gemini · PostgreSQL

## Build phases

1. **Foundation** — backend skeleton, one agent + one tool end to end ✅
2. **The team** — orchestrator + specialists, handoffs, sessions ✅
3. **Safety** — guardrails, refund auto-cap, human approval + Decision Card ✅
4. **Knowledge** — doc parsing, RAG, grounding guardrail ✅
5. **Comms** — SMTP themed mailer + feedback form ✅
6. Frontend — marketing pages, auth, dual dashboard
7. Demo — the guided playground on seed data
8. Commercialise — pricing, integration requests, analytics
