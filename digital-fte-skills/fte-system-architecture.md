---
name: fte-system-architecture
description: Design and lock the end-to-end architecture for the Digital FTE Customer Support Agent before any code is written. Use when the user asks to plan the system, design the architecture, define the data flow, decide component boundaries, "see the end from the beginning", review a build plan, or when starting a new phase or feature and the flow isn't yet clear end-to-end. Produces a bounded blueprint (components, contracts, data flow, failure paths) that every other skill builds against. Targets the OpenAI Agents SDK + Gemini + FastAPI (uv) + Next.js + PostgreSQL stack defined in the platform spec.
---

# FTE System Architecture

Design the whole path before building any part. No feature starts until its flow
is clear from customer message to logged action. This is the source blueprint;
the backend, frontend, agent, data, and auth skills all conform to it.

**Locked stack (from the spec, non-negotiable):** Next.js (Tailwind + shadcn) →
FastAPI on `uv`/`uvicorn` → **OpenAI Agents SDK** runtime driving **Gemini** via
its OpenAI-compatible endpoint → typed tool layer (the only door to data) →
**PostgreSQL** (+ a vector store for RAG). Multi-tenant by `business_id` from day one.

## Golden rules
1. **See the end from the beginning.** Never start a feature you can't trace end to end (input → persisted result → UI).
2. **Contracts before code.** Define the interface (request, response, data shape) first; implementations swap behind it.
3. **One steady path.** Mock-first, then swap real integrations behind the same interface. No mid-build rewrites.
4. **Every action is auditable.** If a step changes state, it writes an audit log / escalation record. No silent effects.
5. **Tools are the frontier.** The model never touches PostgreSQL directly — every read/write goes through a typed tool.
6. **Humans own money-moving decisions.** Anything over the auto-cap or out of policy pauses for human approval.

## Instructions

### Step 1: State the flow in one line
Write the end-to-end sentence before anything else.
> "Customer message → orchestrator routes → specialist reasons → calls a tool → tool acts/persists → (if risky) pauses for human approval → UI reflects it."

If you can't write this for the feature, stop and clarify scope.

### Step 2: Fix the component map
```
Next.js (chat · dual dashboard · demo)  --HTTPS/JSON (authed)-->  FastAPI (uv/uvicorn)
        |                                                              |
   Tailwind + shadcn UI                              Auth + Audit middleware
   customer <-> seller ModeToggle                                     |
                                              ┌──── OpenAI Agents SDK Runner ────┐
                                              │  Orchestrator (triage)            │
                                              │    ├─► Support/FAQ                 │
                                              │    ├─► Orders                      │
                                              │    ├─► Products                    │
                                              │    └─► Refunds ──► human approval  │
                                              │  guardrails: input · output · tool │
                                              └──────────────┬────────────────────┘
                                                             │ tools only (frontier)
                    order_lookup · product_catalog · policy_retriever ·
                    refund_processor(gated) · send_mailer · human_escalation
                                                             │
                              PostgreSQL (records + audit)  +  vector store (RAG)
                                                             │
                              Gemini (via OpenAI-compatible endpoint)
```
Each box owns one responsibility. Cross-box calls happen only through defined contracts (Step 3).

### Step 3: Define the contracts (the seams)
For every boundary, name inputs, outputs, and failure. Minimum contracts:
- **UI → API:** `POST /chat {message, session_id} -> {reply, session_id, actions[]}`; `GET /dashboard/escalations`; `POST /escalations/{id}/decision {approve|adjust|decline, reason?}`.
- **API → agent runtime:** `Runner.run(orchestrator, input, session) -> result.final_output` (the Runner owns the tool loop, handoffs, and approval pauses).
- **Agent → tool:** typed `@function_tool` signature; returns a typed Pydantic result (scoped fields only).
- **Tool → data:** a `store.*` / `db.*` function filtered by `business_id`; same signature for mock and real.
Contracts are frozen per phase. Changing one is an architecture decision, not a code tweak.

### Step 4: Map the data flow and state ownership
| Data | Owner | Now (mock) | Prod |
|---|---|---|---|
| Conversation memory | Agents SDK Session (via API) | in-memory session | PostgreSQL / Redis |
| Orders | data layer | mock dict | orders table |
| Products | data layer | mock catalog | products table |
| Policies / KB | RAG store | keyword search | vector store (pgvector or managed) |
| Escalations / Decision Cards | data layer | mock list | escalations table |
| Audit log | data layer | in-memory list | audit_logs table |
State lives in exactly one owner. UI never holds source-of-truth state; it renders server state. Every row carries `business_id`.

### Step 5: Draw the failure paths
Define the unhappy path BEFORE the happy path:
- Unknown order id → `order_lookup` returns not-found → agent asks to recheck.
- Refund over auto-cap OR out of policy → `refund_processor` does not execute → **Decision Card** created → run pauses for human approval.
- KB miss → grounding output guardrail trips (no `source_ref`) → agent states it can't answer → escalates.
- Identity not verified → tool refuses account-specific action until order_id + email match.
- Backend down → UI shows explicit reconnect hint.
A feature isn't designed until its failure paths are named.

### Step 6: Phase it
Each phase ends in a demoable, working slice:
1. **Foundation** — `uv` backend, FastAPI skeleton, PostgreSQL seed DB, `gemini_model()` factory, one agent + one tool end to end (boots on `mock`).
2. **The team** — orchestrator + Support/Orders/Products/Refunds specialists, handoffs, sessions.
3. **Safety** — input/output/tool guardrails, refund auto-cap, human approval + Decision Card.
4. **Knowledge** — doc parsing, RAG, grounding guardrail, policy checks.
5. **Comms** — SMTP themed mailer + feedback form.
6. **Frontend** — marketing pages (SEO/GEO/AEO), auth, dual dashboard, escalation queue.
7. **Demo** — the guided playground on seed data (the GTM centrepiece).
8. **Commercialise** — pricing tiers, integration request flow, analytics.
Never split a phase across a non-working state.

### Step 7: Gate check before build
A design passes only if all are true:
- [ ] One-line flow written.
- [ ] Every boundary has a frozen contract.
- [ ] State owner named for each data type (with `business_id` tenancy).
- [ ] Failure paths defined, including the human-approval path for gated actions.
- [ ] Phase ends in a working, demoable slice.

## Example
User: "Add order tracking."
1. Flow: "message with order id → orchestrator → Orders agent → `order_lookup` (identity-checked) → status summary → chat."
2. Contract: `order_lookup(order_id: str, email: str) -> OrderStatus`; data via `store.get_order` filtered by `business_id`.
3. State owner: orders = data layer.
4. Failure: unknown id → not-found → agent asks to recheck; unverified identity → refuse until email matches.
5. Phase: fits Phase 2 (the team) on mock. Demoable. Gate passes → build.

## Troubleshooting
- **Mid-build rewrite.** A contract wasn't frozen. Define the seam first, implement behind it.
- **"Works but nothing shows in UI".** State owner unclear. Assign one owner; UI renders it.
- **Silent state change.** Action without a log. Every state-changing tool writes an audit/escalation record.
- **Scope creep.** Feature not traced end to end. Apply Step 1; if no single-line flow, defer.
- **Model can't call tools / structured output flaky.** Gemini-via-SDK tool-calling not validated. Test one tool + one handoff end to end before scaling the agent team (highest-risk integration point).
