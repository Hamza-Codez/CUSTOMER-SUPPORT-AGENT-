---
name: fte-system-architecture
description: Design and lock the end-to-end architecture for the Digital FTE Customer Support Agent before any code is written. Use when the user asks to plan the system, design the architecture, define the data flow, decide component boundaries, "see the end from the beginning", review a build plan, or when starting a new phase or feature and the flow isn't yet clear end-to-end. Produces a bounded blueprint (components, contracts, data flow, failure paths) that every other skill builds against.
---

# FTE System Architecture

Design the whole path before building any part. No feature starts until its flow
is clear from customer message to logged action. This is the source blueprint;
the backend, frontend, agent, data, and auth skills all conform to it.

## Golden rules
1. **See the end from the beginning.** Never start a feature you can't trace end to end (input to persisted result to UI).
2. **Contracts before code.** Define the interface (request, response, data shape) first; implementations swap behind it.
3. **One steady path.** Mock-first, then swap real integrations behind the same interface. No mid-build rewrites.
4. **Every action is auditable.** If a step changes state, it must produce a log/ticket. No silent effects.

## Instructions

### Step 1: State the flow in one line
Write the end-to-end sentence before anything else.
> "Customer message → agent reasons → picks a tool → acts → persists → UI reflects it."
If you can't write this for the feature, stop and clarify scope.

### Step 2: Fix the component map
```
Next.js (chat + dashboard)  --HTTP/JSON-->  FastAPI (orchestration, memory, logging)
        |                                          |
   Tailwind + shadcn UI                    LangGraph ReAct agent
                                                   |
                          tools: search_kb | track_order | process_refund
                                 | create_ticket | escalate_to_human
                                                   |
                          data layer (mock now -> Supabase + pgvector)
```
Each box owns one responsibility. Cross-box calls happen only through defined contracts (see Step 3).

### Step 3: Define the contracts (the seams)
For every boundary, name: inputs, outputs, and failure. Minimum contracts:
- **UI to API:** `POST /chat {message, session_id} -> {reply, session_id, provider}`; `GET /tickets`.
- **API to agent:** `agent.invoke({messages}) -> {messages}`.
- **Agent to tool:** typed function signature; tool returns a plain string result.
- **Tool to data:** a `store.*` function; same signature for mock and real.
Contracts are frozen per phase. Changing one is an architecture decision, not a code tweak.

### Step 4: Map the data flow and state ownership
| Data | Owner | Now | Prod |
|---|---|---|---|
| Conversation memory | API (`SESSIONS`) | in-memory dict | Supabase/Redis |
| Orders | data layer | mock dict | orders API / table |
| Tickets | data layer | mock list | Supabase table |
| Knowledge | data layer | keyword search | pgvector |
State lives in exactly one owner. UI never holds source-of-truth state; it renders server state.

### Step 5: Draw the failure paths
For each tool/endpoint, define the unhappy path BEFORE the happy path:
- Unknown order id -> tool returns not-found -> agent asks to recheck.
- Refund on non-refundable order -> tool refuses -> agent escalates.
- KB miss -> agent states it can't answer -> escalates.
- Backend down -> UI shows explicit reconnect hint.
A feature isn't designed until its failure paths are named.

### Step 6: Phase it
Order phases so each ends in a demoable, working slice:
1. Agent + tools on mock (works end to end, zero setup).
2. Real data (Supabase + pgvector) behind the same `store.*` contracts.
3. Streaming UI.
4. Auth + onboarding.
5. Deploy.
Never split a phase across a non-working state.

### Step 7: Gate check before build
A design passes only if all are true:
- [ ] One-line flow written.
- [ ] Every boundary has a frozen contract.
- [ ] State owner named for each data type.
- [ ] Failure paths defined.
- [ ] Phase ends in a working, demoable slice.

## Example
User: "Add order tracking."
1. Flow: "message with ORD-id -> agent -> track_order -> order summary -> chat."
2. Contract: `track_order(order_id: str) -> str`; data via `store.get_order`.
3. State owner: orders = data layer.
4. Failure: unknown id -> not-found string -> agent asks to recheck.
5. Phase: fits Phase 1 (mock). Demoable. Gate passes -> build.

## Troubleshooting
- **Symptom: mid-build rewrite.** Cause: a contract wasn't frozen. Fix: define the seam first, implement behind it.
- **Symptom: "works but nothing shows in UI".** Cause: state owner unclear. Fix: assign one owner; UI renders it.
- **Symptom: silent state change.** Cause: action without a log. Fix: every state-changing tool writes a ticket.
- **Symptom: scope creep.** Cause: feature not traced end to end. Fix: apply Step 1; if no single-line flow, defer.
