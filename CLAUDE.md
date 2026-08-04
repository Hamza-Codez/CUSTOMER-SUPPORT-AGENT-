# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A "Digital FTE" — an AI agent that runs e-commerce frontline support (order
tracking, grounded policy answers, product comparison, policy-checked refunds)
with humans owning every decision that moves money.

Stack: FastAPI + OpenAI Agents SDK + PostgreSQL (`backend/`), Next.js 16
(`frontend/`). Groq serves both model tiers; Gemini serves embeddings.

## Read this before planning anything

The repo is **mid-correction**. Phases 1–8 shipped and were then audited by the
user as "a puppet show": mock-first, high test volume, no real product path.
That audit and its answer are the current marching orders.

| Document | What it is | Authority |
|---|---|---|
| `CRITIC.md` | The user's audit, in their own words | Why the pivot exists |
| `RESOLVE.md` | The correction spec — naming, target architecture, phase order | **Supersedes SPEC.md on conflict** |
| `INTENT.md` | Product intent | Still valid |
| `SPEC.md` | Original technical spec | Valid except where RESOLVE.md restates it |
| `digital-fte-skills/*.md` | The build skills the code conforms to | Load the matching one before building |
| `docs/DEPLOYING.md` | Vercel + Supabase deployment, and its traps | Current |

Three names are now locked (`RESOLVE.md §0`) and must not blur again — the audit
says letting them blur was the original mistake:

- **Aperture** — the platform shell: marketing, auth, onboarding, profile,
  integrations, dashboard, trial billing.
- **Demo** — an on-rails trailer. Scripted, never touches real tools or data.
- **LIGHTRON** — the real product. No mocks anywhere in its answer path.

Two standing instructions from `RESOLVE.md` that override normal habits:

1. **Plan each phase before coding.** The user approves plans, not diffs.
2. **Do not write exhaustive test suites.** Golden-path smoke checks only
   (`§8.4`). The 445-test suite already here is part of what is being corrected,
   not a model to extend.

Where existing code disagrees with a document, the code is often right and
deliberately so — deviations are documented in commit messages, in the backend
README, and in the docstring of the file that deviates. Read the docstring before
"fixing" a mismatch.

## Commands

```bash
# Backend (uv-managed; Python 3.12+)
cd backend
uv sync
uv run pytest                                   # full suite (~4 min)
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
in-memory store. Keep that working for local dev — but `mock` is explicitly not
an acceptable LIGHTRON answer path, and `ENVIRONMENT=production` refuses to boot
on it.

## In-flight migration: two model tiers on Groq

`backend/app/core/model.py` and `config.py` are **uncommitted work in progress**.
Understand this before touching either.

`RESOLVE.md §4` put reasoning on Gemini and voice on Groq. Gemini's free tier is
20 requests/day — about ten conversations for the whole platform — so reasoning
moved to Groq as well:

| Tier | Factory | Env | Role |
|---|---|---|---|
| Reasoning | `reasoning_model()` | `GROQ_REASONING_MODEL` | Triage, tool selection, handoffs, rulings |
| Voice | `voice_model()` | `GROQ_VOICE_MODEL` | Renders decided facts as prose; calls no tools, so it cannot invent one |
| Embeddings | `app/rag/embeddings.py` | `GEMINI_API_KEY` | Separate quota, so retrieval survives an exhausted chat budget |

Both tiers go through `AsyncOpenAI` → `OpenAIChatCompletionsModel` against
`https://api.groq.com/openai/v1`, never a bare model string (that would send the
call to OpenAI). Tracing stays disabled — the SDK uploads to OpenAI's backend.

Known inconsistencies the partial migration left behind, all real:

- `gemini_model = reasoning_model` is a compatibility alias at the foot of
  `model.py`; `agents/orchestrator.py` and `tests/conftest.py` still import it.
  New code asks for the tier it means.
- `Settings.model_provider` is still `Literal["mock", "gemini"]` although the
  non-mock value now selects Groq.
- Three tests in `tests/test_deployment.py` fail, because `deployment_problems()`
  gained a `GROQ_API_KEY` check the tests predate. Fix the tests, not the check.

Groq model IDs churn and retired ones vanish without notice, so neither default
is pinned in code — verify against Groq's models page rather than trusting them.

## Architecture

### The tool layer is the only door to data

Nothing outside `backend/app/tools/` touches the store. The model never sees SQL
and never receives a row it did not request through a tool. `RESOLVE.md §7`
pushes this one level further: tools should call a `DataAdapter` protocol, so
swapping scraped-store data (Flavour A) for a real store API (Flavour B) is a
binding change rather than a rewrite.

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

### Behaviour is a table, not a prompt

`app/scenarios/__init__.py` holds `SCENARIOS` — one row per scenario, each naming
its triggers, the facts it needs, the tools it may use, the decision rule, the
boundary it stops at (`ASK` / `ESCALATE` / `APPROVAL` / `REFUSE`) and the shape of
the reply (`CARD` / `PROSE` / `CARD_AND_PROSE`).

Three consumers, which is the entire point: specialist instructions are
**generated** from it (`render_playbook`), the action guardrail reads
`escalates_when`, and the renderer reads `response` to decide whether an answer is
built from tool data or written by the voice tier. `tools_for()` derives least
privilege from the same table — a specialist cannot reach a tool no scenario it
owns declared. Adding behaviour means adding a row, not editing four prompts and
hoping they agree.

`CARD` scenarios (order lists, case summaries, cart) skip the voice tier
entirely. That is the answer to "responses look average": a list rendered from
adapter data cannot be phrased badly.

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
the agent reasons about. None of them becomes a 500, and none becomes a generic
apology — each maps to a `Boundary` in the scenario table.

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
- Against a transaction pooler (Supabase 6543, pgBouncer) set
  `DB_TRANSACTION_POOLER=true`, or asyncpg's statement cache fails intermittently
  under load.

### The mock provider is a real `Model`, not a bypass

`app/core/mock_model.py` implements the SDK's `Model` interface, so the Runner
drives it exactly as it drives a live provider: real handoffs, real tool calls,
real tenancy and audit. Only the language model is substituted. It pins our
wiring, never the model's judgement — a passing mock test is not evidence about
Groq or Gemini, which is precisely the confusion the audit called out.

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

The seeded knowledge base is `app/db/knowledge/*.md` — real documents, parsed by
both stores. Citations use authored anchors (`{#damaged-goods}`) so rewording a
heading cannot break a `source_ref` already in an audit log. Per-store KBs built
by scraping (`app/rag/site_scan.py`, `RESOLVE.md §6.1`) are the direction of
travel.

### Three ways into the API

`app/main.py` is one FastAPI app serving three audiences that authenticate
differently. Never merge the paths:

| Surface | Auth | Routes |
|---|---|---|
| Seller dashboard | JWT from `/auth/login`, or `DEV_TOKENS` | `/chat`, `/dashboard/*`, `/site-keys`, `/onboarding/*` |
| Embedded widget | **site key**, origin-scoped | `/chat/public`, `/widget/config`, `/widget.js` |
| Email recipients | signed one-click token | `/feedback/{token}` |

The site key is a public credential with its own dependency (`SiteKeyDep`) — it
must never be folded into `require_tenant`. Operator-only routes go through
`require_operator`.

### Deployment refuses to be half-configured

`Settings.deployment_problems()` returns *every* misconfiguration at once, and
`ENVIRONMENT=production` refuses to boot on any of them. Each item is something
that would otherwise work silently and wrongly: the mock provider answering from
a lookup table, the in-memory store discarding data per request, the documented
`ops-token` handing a stranger the refund queue, a per-instance JWT secret
signing users out at random. Adding a config knob that can fail quietly means
adding a check here.

### Frontend

**`frontend/AGENTS.md` requires reading `node_modules/next/dist/docs/` before
writing frontend code** (`frontend/CLAUDE.md` is just `@AGENTS.md`). Next 16 is
newer than most training data: `params`, `searchParams`, `cookies()` and
`headers()` are async-only, and Tailwind v4 has no config file (tokens are
`@theme` in `app/globals.css`).

Routes today: marketing (`/`, `/features`, `/pricing`, `/faq`), auth (`/signup`,
`/login`), then `/onboarding`, `/integrations`, `/demo`, `/dashboard`.

Design tokens are defined once in `globals.css`; a hex literal in a component is
a bug. All backend calls go through `lib/api.ts`. Action chips are built from
real tool results, so a chip cannot appear unless the thing it names happened —
extend that rule rather than working around it, since the audit's central charge
was that the UI displayed strings the agent never produced.

## Verification standard

Probe the real thing and say plainly what was not verified. The repo's READMEs
carry explicit "Verified" and "Not verified" sections — keep them honest rather
than tidy. `RESOLVE.md §11` raises the bar: acceptance is a live grounded
conversation on a real store at a deployed URL, not a passing suite.

Known unverified areas: real SMTP delivery, and the visual/interaction behaviour
of the frontend (there is no browser in this environment).

Provider quotas are a product constraint, not a dev annoyance. Gemini's free tier
is **20 requests/day** on `gemini-3.6-flash` (what `gemini-flash-latest` resolves
to) — which is why chat moved to Groq. `gemini-2.5-flash` is listed by the API
but 404s on new keys. Embeddings draw on a separate quota.
