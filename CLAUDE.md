# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A "Digital FTE" — an AI agent that runs e-commerce frontline support (order
tracking, grounded policy answers, product comparison, policy-checked refunds)
with humans owning every decision that moves money.

`INTENT.md` is the product intent, `SPEC.md` the technical spec, and
`digital-fte-skills/*.md` the build skills the code conforms to. When those
disagree with the code, the code is usually right and deliberately so — the
deviations are documented in commit messages and the backend README.

Stack: FastAPI + OpenAI Agents SDK + Gemini + PostgreSQL (`backend/`), Next.js 16
(`frontend/`).

## Commands

```bash
# Backend (uv-managed; Python 3.12+)
cd backend
uv sync
uv run pytest                                   # full suite
uv run pytest tests/test_tools.py               # one file
uv run pytest -k "refund and cap"               # by name
uv run pytest tests/test_postgres.py -v         # skips unless DATABASE_URL is set
uv run uvicorn app.main:app --reload            # :8000

uv run python scripts/init_db.py                # schema + seed + embed the KB
uv run python scripts/ingest_kb.py              # re-embed after editing knowledge docs

# Frontend
cd frontend
npm install
npm run dev                                     # :3000
npm run build                                   # also type-checks
npx eslint .                                    # errors here are usually real bugs
```

Everything boots with **zero setup**: `MODEL_PROVIDER`, `EMBEDDING_PROVIDER` and
`EMAIL_PROVIDER` all default to `mock`, and an empty `DATABASE_URL` selects the
in-memory store. Do not break that — the whole test suite depends on it.

## Architecture

### The tool layer is the only door to data

Nothing outside `backend/app/tools/` touches the store. The model never sees SQL
and never receives a row it did not request through a tool.

### The model never names a sensitive target

This is the rule the codebase keeps returning to. Anything the model can supply
as a parameter, a customer can talk it into supplying, so the target of a
sensitive action never appears in a tool signature:

| Value | Comes from |
|---|---|
| `business_id` | the caller's token, via `RunContextWrapper` |
| Which order a refund may touch | `verified_orders`, written by `order_lookup` on an email match |
| Email recipient | `verified_email` — `send_summary_email` has **no** recipient parameter |

`SPEC.md §6.2` sketches `send_mailer(..., recipient, ...)`. Dropping `recipient`
was deliberate; do not "fix" it to match the doc.

### Policy lives in code, never in a prompt

The refund cap and window are in `app/guardrails/refund_guard.py` and are never
stated in any prompt, so there is nothing to argue the model out of. This is not
theoretical: the live model was observed ignoring an explicit "never answer this
yourself" instruction and inventing product prices. Two things fix that class of
problem — forcing the shape of the move (`ModelSettings(tool_choice="required")`
on the Orchestrator and the retrieving specialists) and judging **recorded
evidence** rather than the model's account of itself (`app/guardrails/grounding.py`
reads `tools_used`, not the reply text).

### Failures are typed values

A missing order, a failed identity check, a retrieval miss: all normal results
the agent reasons about. None of them become a 500.

### Two stores, one contract

`app/db/base.py` defines `Store`; `mock_store.py` and `postgres_store.py` both
implement it, and `tests/test_postgres.py` asserts they return identical records.
Anything added to one must be added to the other, or the parity tests fail.

Postgres specifics that bite:
- Everything lives in an **`fte` schema**, never `public` — the target database
  hosts unrelated projects with colliding table names (`orders`, `products`,
  `users`). Queries in `seed.sql` are schema-qualified for the same reason.
- `create table if not exists` does nothing to an existing table, so new columns
  also need an `alter table ... add column if not exists` in the migrations block
  at the end of `schema.sql`.
- The DSN password must be URL-encoded (`#`→`%23` etc.); a raw `#` truncates the
  URL and the port parses as garbage.

### The mock provider is a real `Model`, not a bypass

`app/core/mock_model.py` implements the SDK's `Model` interface, so the Runner
drives it exactly as it drives Gemini: real handoffs, real tool calls, real
tenancy and audit. Only the language model is substituted. It pins our wiring,
never the model's judgement — so a passing mock test is not evidence about Gemini.

Two rules inside it that were bugs first: intent comes from the **latest** user
message (falling back to conversation history only when the latest carries none),
and tool results are read only from the **current turn**.

### Human approval resumes the original run

`function_tool(needs_approval=...)` → `RunResult.interruptions` →
`RunState.to_json()` stored on the escalation → operator decides later →
`RunState.from_json()` (a coroutine — **await it**) → `.approve()` →
`Runner.run(agent, state)` **with the state alone**. Passing `context=` or
`session=` on resume replays the original message and pauses again.

Serialising the state needs `context_serializer=` (see `_plain_context` in
`main.py`) because the tenant context holds a live asyncpg pool. And the run's
evidence must be restored onto the fresh context, or the guardrails block the
very action the operator just approved.

### Retrieval is hybrid on purpose

`app/rag/retriever.py`: keyword **admits and rejects**; vectors **only admit**.
Measured against this corpus, Gemini embeddings put on-topic questions at
0.607–0.780 and off-domain at 0.381–0.582 — a 0.025 gap, far too narrow to place
a rejection threshold in. So `RETRIEVAL_VECTOR_FLOOR` sits *above* the highest
observed miss and keyword does the rejecting. **A miss must return nothing**;
retrieval that always answers launders a guess into a citation.

The knowledge base is `app/db/knowledge/*.md` — real documents, parsed by both
stores. Citations use authored anchors (`{#damaged-goods}`) so rewording a
heading cannot break a `source_ref` already in an audit log.

### Frontend

**`frontend/AGENTS.md` requires reading `node_modules/next/dist/docs/` before
writing frontend code.** Next 16 is newer than most training data: `params`,
`searchParams`, `cookies()` and `headers()` are async-only, and Tailwind v4 has
no config file (tokens are `@theme` in `app/globals.css`).

Design tokens are defined once in `globals.css`; a hex literal in a component is
a bug. All backend calls go through `lib/api.ts`. Action chips are built from
real tool results, so a chip cannot appear unless the thing it names happened.

## Verification standard

Probe the real thing and say plainly what was not verified. The repo's READMEs
carry explicit "Verified" and "Not verified" sections — keep them honest rather
than tidy. Known unverified areas: real SMTP delivery, and the visual/interaction
behaviour of the frontend (there is no browser in this environment).

Gemini's free tier is **20 requests/day** on `gemini-3.6-flash` (what
`gemini-flash-latest` resolves to) at ~2 model calls per conversation turn.
Budget live checks; `gemini-2.5-flash` is listed by the API but 404s on new keys.
Embeddings use a separate quota from chat.
