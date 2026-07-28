# FTE Agent Platform — Technical Specification

*Companion to `FTE_Agent_Platform_Intent.md`. That document is the "why" and "what"; this is the "how." Written against the confirmed behaviour of the OpenAI Agents SDK (Python) driving Gemini through its OpenAI-compatible endpoint. Where the SDK or Gemini model names may have shifted, it is flagged inline — verify before locking.*

**Stack:** Next.js (frontend) · FastAPI on `uv` + `uvicorn` (backend) · PostgreSQL (data) · OpenAI Agents SDK (agent runtime) · Gemini API (model)

---

## 1. Scope of This Document

This spec covers the runtime architecture, the agent/tool/guardrail design, the data model, the API surface, the RAG pipeline, the frontend structure, and two detailed drafts requested for the build: the **seller-facing pricing-tier feature comparison** (§16) and the **demo playground step-flow** (§15). It intentionally stops short of line-by-line code — it's the blueprint a developer builds from.

---

## 2. Architecture Overview

```
                         ┌───────────────────────────────────────────┐
                         │              FRONTEND (Next.js)             │
                         │  Landing · Pricing · Auth · Demo · Dashboard│
                         └───────────────┬─────────────────────────────┘
                                         │  HTTPS / JSON  (authenticated)
                         ┌───────────────▼─────────────────────────────┐
                         │            BACKEND (FastAPI / uv)            │
                         │                                             │
                         │  API routes ──► Auth + Audit middleware     │
                         │       │                                     │
                         │       ▼                                     │
                         │  ┌──────────── Agent Runtime ────────────┐  │
                         │  │  Runner (loop, handoffs, approvals)   │  │
                         │  │  Orchestrator ─► Support / Orders /   │  │
                         │  │                 Products / Refunds    │  │
                         │  │  Guardrails (input · output · tool)   │  │
                         │  └──────────────┬────────────────────────┘  │
                         │                 │ tools only (the frontier) │
                         │       ┌─────────▼─────────┐                 │
                         │       │   TOOL LAYER      │                 │
                         │       │ orders·products·  │                 │
                         │       │ policies·refunds· │                 │
                         │       │ email·escalation  │                 │
                         │       └───┬──────────┬────┘                 │
                         └───────────┼──────────┼──────────────────────┘
                                     │          │
                       ┌─────────────▼──┐   ┌───▼───────────┐   ┌──────────────┐
                       │  PostgreSQL    │   │  RAG store    │   │  Gemini API  │
                       │ (records+audit)│   │ (parsed docs) │   │ (via OpenAI  │
                       └────────────────┘   └───────────────┘   │  compat SDK) │
                                                                └──────────────┘
```

**The one rule that shapes everything:** the model never touches PostgreSQL directly. Every read and write passes through a typed tool in the tool layer. Tools are the audited, rate-limited, least-privilege border between the LLM and real data.

---

## 3. Tech Stack & Rationale

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js (App Router) | Page-based routing for the multi-page site + demo; SSR for SEO/GEO/AEO on marketing pages |
| Backend | FastAPI, run by `uvicorn` | Async, typed (Pydantic), fast; native fit for streaming agent responses |
| Packaging | `uv` | Fast, reproducible Python dependency + venv management |
| Agent runtime | OpenAI Agents SDK (Python) | Built-in agent loop, handoffs, guardrails, sessions, tracing, and resumable approval flows |
| Model | Gemini (via OpenAI-compatible endpoint) | Cost/capability target; drops into the SDK with a custom client |
| Data | PostgreSQL | Relational records + audit log; dummy/seed DB for demos, same schema for production |
| Retrieval | Vector store over parsed docs | Grounded, no-invention answers |
| Email | SMTP | Themed summary + feedback mailer |

---

## 4. Model Layer — Gemini via the Agents SDK

The Agents SDK is designed for OpenAI models but works against any OpenAI-compatible endpoint, and Gemini exposes exactly that. The confirmed wiring is: point an `AsyncOpenAI` client at Gemini's OpenAI-compatible base URL, wrap it in a chat-completions model, and hand that model to each agent.

```python
# core/model.py  (illustrative — your own minimal version)
import os
from agents import AsyncOpenAI, OpenAIChatCompletionsModel, set_tracing_disabled

def gemini_model(model_name: str | None = None):
    client = AsyncOpenAI(
        api_key=os.environ["GEMINI_API_KEY"],
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    set_tracing_disabled(True)  # SDK tracing uploads to OpenAI; disable or route to your own processor
    return OpenAIChatCompletionsModel(
        model=model_name or os.environ["GEMINI_MODEL"],  # keep the model string in env
        openai_client=client,
    )
```

**Notes & flags:**
- **Model name lives in `.env`** (`GEMINI_MODEL`), never hardcoded. Gemini's flash-tier model names have moved fast (2.0 → 2.5 → newer). Confirm the current model code and its input/output token limits before launch.
- **Tracing:** the SDK's built-in tracing targets OpenAI's backend. With Gemini, either disable it (`set_tracing_disabled(True)`) or attach a custom trace processor so you don't leak data or hit auth errors.
- **Alternative path — LiteLLM:** the SDK also supports a LiteLLM adapter covering 100+ models, useful if you later want to A/B a model or fail over. Keep the model construction behind one `gemini_model()`-style factory so swapping providers is a one-line change.
- **Function-calling parity:** validate that Gemini's tool-calling and structured-output behaviour matches what the SDK expects (this is the single highest-risk integration point — test the refund tool + a handoff end to end early).

---

## 5. Agent Architecture

### 5.1 Primitives used

The SDK gives five building blocks, all of which this system uses:

- **Agents** — an LLM with instructions, a scoped tool set, and optional handoffs/guardrails.
- **Function tools** — plain Python functions exposed to the agent via a decorator; the SDK auto-generates the schema (Pydantic-validated) from the signature.
- **Handoffs** — transfer of the conversation from one agent to another within a single run; the receiving agent sees prior history unless filtered.
- **Guardrails** — input, output, and per-tool validation that can trip a "tripwire" and stop the run.
- **Sessions** — persistent conversation memory across turns with no manual state plumbing.
- **Runner** — drives the tool loop, switches agents on handoff, and can **pause for human approval** before executing a gated action.

### 5.2 The agent team

| Agent | Job | Tools it may use | Can hand off to |
|---|---|---|---|
| **Orchestrator (Triage)** | Read intent, route to the right specialist | *(none — routing only)* | all specialists |
| **Support/FAQ** | Grounded answers from parsed docs | `policy_retriever` | Orchestrator |
| **Orders** | Verify identity, report order status | `order_lookup` | Refunds, Orchestrator |
| **Products** | Explain & compare products | `product_catalog` | Orchestrator |
| **Refunds** | Policy check + prepare/execute refund | `policy_retriever`, `order_lookup`, `refund_processor`, `human_escalation` | Human (approval) |

Two patterns are available and both are used:
- **Handoff** (transfer the whole conversation) for a clean role switch — e.g., Orders → Refunds when a status check turns into a refund.
- **Agent-as-tool** (call a specialist for a sub-answer without transferring) — e.g., Support calls Products for a quick comparison mid-answer.

### 5.3 Sessions & context

Each conversation maps to a Session so the FTE remembers what's been said (verified identity, the order in question) without re-asking. The business's **context feed** (policies, catalog, tone, thresholds) is injected as agent instructions + retrievable data, not stuffed into every prompt — keeping token cost down.

---

## 6. Tool Layer — The Data Frontier

### 6.1 Pattern

Every tool is a typed Python function registered with the SDK's function-tool decorator; the SDK generates and validates the schema. Tools return **only the fields the agent needs**, in a structured shape, to minimise reasoning tokens.

```python
# tools/orders.py  (illustrative)
from agents import function_tool
from pydantic import BaseModel

class OrderStatus(BaseModel):
    order_id: str
    status: str
    last_update: str
    carrier: str | None
    eta: str | None

@function_tool
async def order_lookup(order_id: str, email: str) -> OrderStatus:
    """Return the status of an order after verifying it belongs to the email."""
    # 1. auth check  2. scoped SELECT  3. write audit log  4. return typed subset
    ...
```

### 6.2 Tool catalog

| Tool | Access | Inputs | Returns | Guarded by |
|---|---|---|---|---|
| `order_lookup` | read | order_id, email | typed status subset | identity match + audit log |
| `product_catalog` | read | query / product_ids | product + comparison fields | cache |
| `policy_retriever` | read (RAG) | question, topic | grounded passage + source ref | confidence threshold |
| `refund_processor` | **write, gated** | order_id, amount, reason | refund result / pending-approval | action guardrail + human approval above cap |
| `send_mailer` | write | template, recipient, payload | send status | idempotency key |
| `human_escalation` | write | decision-card payload | escalation id | always logged |

### 6.3 Optimisation strategy (the cost engine)

- **Least privilege:** each agent is constructed with only the tools its role needs — Support literally cannot call `refund_processor`.
- **Scoped returns:** tools SELECT and return only required columns; no `SELECT *` reaching the model.
- **Caching:** slow-changing reads (policies, catalog) are cached; the agent doesn't re-fetch every turn.
- **Idempotent writes:** `refund_processor` and `send_mailer` use idempotency keys so a retried run can't double-refund or double-email.
- **Minimal calls:** the orchestrator sequences lookups deliberately rather than firing redundant queries.
- **Full observability:** every tool call is logged with duration and (rough) token cost for later tuning.

---

## 7. Guardrails Specification

The SDK supports three guardrail scopes; the system uses all three.

### 7.1 Input guardrails (before the first agent runs)
Run on the incoming message; trip a tripwire to reject early.
- **Scope guard** — is this in-domain (support/orders/products/refunds)? Off-topic → polite redirect.
- **Safety/injection guard** — screen hostile input and prompt-injection attempts.
- (Identity is enforced at the tool layer, not here, since it's action-specific.)

### 7.2 Output guardrails (after the final agent, before the reply reaches the user)
- **Grounding guard** — does the answer trace to a retrieved source? Ungrounded policy/product claims trip the wire → fall back to "let me get a person" rather than guess.
- **Tone guard** — keep replies polite and on-brand.

### 7.3 Tool guardrails (around each function-tool call)
This is where money-moving safety lives, because it runs on **every invocation** even deep inside a handoff chain.
- **Input tool guardrail on `refund_processor`** — verify identity is confirmed, amount ≤ configured auto-cap, and the policy check passed. Otherwise skip execution and route to human approval.
- **Output tool guardrail** — sanity-check results before they re-enter the model.

```python
# guardrails/grounding.py  (illustrative shape)
from agents import output_guardrail, GuardrailFunctionOutput

@output_guardrail
async def must_be_grounded(ctx, agent, output) -> GuardrailFunctionOutput:
    grounded = bool(getattr(output, "source_ref", None))
    return GuardrailFunctionOutput(
        output_info={"grounded": grounded},
        tripwire_triggered=not grounded,   # trip → SDK stops, we escalate instead
    )
```

### 7.4 Human approval (the built-in human-in-the-loop)
The runner can **pause a run for approval** before a gated tool executes. `refund_processor` (above the auto-cap) is configured to require approval — the run halts, a Decision Card is created, and execution resumes only after an operator approves. This is the mechanism behind §8.

---

## 8. Human Handoff & the Decision Card

When a refund exceeds the auto-cap, is out of policy, or the customer is upset/asks for a person:

1. The Refunds agent calls `human_escalation` (or the runner pauses `refund_processor` for approval).
2. A **Decision Card** record is written and pushed to the seller's operator queue (dashboard + optional email/websocket).
3. The card carries everything the human needs to decide in seconds: verified customer, request, the policy that applies, the proposed action, and one-click **Approve / Adjust / Decline (with reason)**.
4. The operator's decision resumes the paused run (or resolves the escalation); the outcome flows back into the same conversation and is fully logged.

**Decision Card payload (JSON shape):**
```json
{
  "escalation_id": "esc_10432",
  "customer": {"name": "Ayesha K.", "verified": true, "via": "order+email"},
  "request": "Refund — Order #10432, item arrived damaged",
  "policy_check": {"rule": "30-day damaged-goods", "result": "eligible"},
  "proposed_action": {"type": "refund", "amount": 59.00, "method": "original"},
  "options": ["approve", "adjust", "decline_with_reason"],
  "created_at": "2026-07-26T10:14:00Z"
}
```

---

## 9. Data Model (PostgreSQL)

Core tables (seed/dummy for demos, same schema in production):

| Table | Key columns | Notes |
|---|---|---|
| `businesses` | id, name, plan_tier, mode | the seller tenant |
| `subscriptions` | id, business_id, tier, billing_cycle, status | monthly/yearly |
| `operators` | id, business_id, email, role | staff who approve handoffs |
| `customers` | id, business_id, email, name | end users |
| `products` | id, business_id, name, attrs (jsonb), price, stock | catalog + comparison fields |
| `orders` | id, business_id, customer_id, status, carrier, eta | tracked |
| `order_items` | id, order_id, product_id, qty, price | line items |
| `policies` | id, business_id, type, source_doc, text | source for RAG + refund checks |
| `refunds` | id, order_id, amount, reason, status, approved_by | status: auto/pending/approved/declined |
| `escalations` | id, business_id, decision_card (jsonb), status, resolved_by | operator queue |
| `conversations` | id, business_id, customer_id, session_id, mode | ties to SDK session |
| `messages` | id, conversation_id, role, content, tool_calls (jsonb) | transcript |
| `audit_logs` | id, actor, action, target, detail (jsonb), ts | **every** sensitive read/write |

`business_id` is the tenancy key on every row — the platform is multi-tenant from day one, and tools always filter by it.

---

## 10. RAG / Knowledge-Base Pipeline

The "parse structure so ready-to-use info is always at hand, no invented answers" requirement, made concrete:

1. **Ingest** — seller uploads policy/FAQ/help docs during onboarding.
2. **Parse** — `rag/parser.py` normalises docs into clean text + metadata (doc type, section).
3. **Chunk & embed** — split into passages, embed, store vectors + source references.
4. **Retrieve** — `policy_retriever` tool takes a question, returns the top passage(s) **with a `source_ref`**.
5. **Ground** — the output grounding guardrail (§7.2) requires that `source_ref` before an answer ships. No source → no claim → escalate or say "I'll check with a person."

Refund policy checks read from the same parsed `policies` so rulings and answers never drift apart.

---

## 11. Backend API (FastAPI)

| Method / Route | Purpose | Auth |
|---|---|---|
| `POST /auth/signup`, `/auth/login` | account + session | public → issues token |
| `POST /chat` | send a message, run the agent, stream reply | customer/session |
| `GET /orders/{id}` | (thin passthrough; real access via tools) | verified |
| `GET /dashboard/escalations` | operator queue | operator |
| `POST /escalations/{id}/decision` | approve/adjust/decline → resumes run | operator |
| `POST /onboarding/context` | upload policies/catalog/tone (context feed) | seller |
| `POST /integrations/request` | seller asks to embed the FTE | seller |
| `POST /webhooks/email` | mailer callbacks | signed |

`/chat` is the hot path: authenticate → load session → run the agent via the Runner (which handles the tool loop, handoffs, and any approval pause) → stream the result → persist transcript + audit.

---

## 12. Auth & Audit Logging

- **Auth** — token-based sessions; customer identity for account actions is additionally proven at the tool layer (order_id + email match) before any record is read or changed.
- **Audit** — `audit_logs` captures every sensitive tool call: who, what action, on what target, when, with a jsonb detail blob. This satisfies the "authenticated flows + retrieval logs" foundation rule and is the backbone of trust for a system that can move money.

---

## 13. Email / SMTP Themed Mailer

After a resolved conversation, `send_mailer` sends a branded (purple/black/zinc-themed) email containing a **summary + short feedback form**. Templates live server-side; sends are idempotent (one summary per resolution). Doubles as passive advertising via a subtle "handled by your FTE" footer.

---

## 14. Frontend (Next.js) Structure

| Route | Type | Purpose |
|---|---|---|
| `/` | SSR marketing | hero + 5–6 sections; SEO/GEO/AEO tuned |
| `/features` | SSR marketing | the FTE "job description" |
| `/pricing` | SSR marketing | tier comparison (§16) |
| `/login`, `/signup` | client | auth → gateway to demo |
| `/demo` | client, gated | the playground (§15) |
| `/dashboard` | client, gated | dual customer/seller view + escalation queue |
| `/integrations` | client | guided embed request |

Shared components: `ChatWidget`, `QuickReplies`, `ProductCompareCard`, `DecisionCard`, `ModeToggle` (customer ↔ seller), `StepCard` (demo). Theme tokens (purple/black/zinc gradient, minimalist) defined once and reused across marketing + app.

---

## 15. DRAFT — Demo Playground Step-Flow

*Goal: a first-timer signs up and, in ~2 minutes of guided clicking, experiences both sides of the FTE on realistic seed data, then lands on pricing/integration wanting it. Every step is a card with a clear clickable — nobody gets lost.*

**Entry:** user signs up → lands in `/demo` → a welcome **StepCard**: "Meet your new full-time employee. Let's watch it work." → **[Start the tour]**

| Step | View | What the user sees / does | The "aha" |
|---|---|---|---|
| 1. Meet the FTE | Customer | Chat opens with quick-reply chips: *Track order · Product help · Refund · Refund policy*. Card: "These are one-tap — try tapping **Track order**." | It's guided, not a blank box |
| 2. Identity gate | Customer | FTE asks for a demo order ID/email (pre-filled sample). Card explains: "It verifies who it's talking to before revealing anything." | It's secure, not reckless |
| 3. Real lookup | Customer | FTE returns a real (seed) order status with carrier + ETA in friendly language. | It reads actual data, not canned text |
| 4. Product compare | Customer | User taps **Product help** → FTE shows a side-by-side `ProductCompareCard` with a **[Proceed]** button. | Support quietly becomes sales |
| 5. Refund — in policy | Customer | User requests a refund that qualifies → FTE explains the policy warmly and prepares it. Card: "Watch what happens with a *harder* one next." | Grounded, polite, policy-driven |
| 6. Refund — needs a human | Customer | User requests an out-of-policy refund → FTE escalates instead of guessing. Card: "Now flip to the seller's side to see what the human gets." → **[Switch to Seller view]** |  Knows its limits |
| 7. The Decision Card | Seller (toggle) | `ModeToggle` flips to operator view; the escalation from step 6 sits in the queue as a **Decision Card** with Approve / Adjust / Decline. User clicks **Approve**. | The "ready to click OK" magic |
| 8. It closes the loop | Customer (toggle back) | The approved outcome appears in the same conversation; a themed summary+feedback email preview is shown. | Seamless, end to end |
| 9. See the ops view | Seller | Quick peek at records, stock, policies, logs — the dual dashboard. | It's an operator, not a toy |
| 10. Convert | — | Final card: "This is your FTE on sample data. Ready for it on *your* store?" → **[See pricing]** and **[Request integration]**. | Clear next step |

**Design rules for the flow:** each step advances only on a click (self-paced), the customer↔seller toggle is the emotional centre (do it at least twice), everything runs on the PostgreSQL seed DB so it feels real, and the tour is skippable for repeat visitors.

---

## 16. DRAFT — Seller-Facing Pricing-Tier Comparison

*Two feature tiers, each billable monthly or yearly (yearly discounted). Tier 1 is anchored at the $20/mo from the brief; Tier 2's price is proposed — set it once you've costed model usage.*

| | **Core** — $20/mo *(yearly: ~$192/yr, 2 months free)* | **Pro** — *$49/mo proposed* *(yearly discounted)* |
|---|---|---|
| **Best for** | Solo sellers & small stores getting started | Growing stores that want automation + embedding |
| Deployment | Hosted dual dashboard | Hosted **+ embedded** on your own site |
| Conversations / month | Included allowance (e.g. 1,000) | Higher allowance (e.g. 10,000) + overage |
| Specialist agents | All 5 (support, orders, products, refunds, triage) | All 5 |
| Knowledge base | Up to N docs | Expanded docs + priority re-index |
| Refund auto-approval cap | Lower cap; rest escalates | Higher configurable cap |
| Escalation / Decision Cards | ✓ | ✓ + priority routing & multiple operator seats |
| Product comparison cards | ✓ | ✓ |
| Themed summary + feedback mailer | ✓ (standard theme) | ✓ (custom branding) |
| Operator seats | 1 | Multiple |
| Analytics | Core metrics (deflection, CSAT) | Full analytics + cost-per-conversation dashboard |
| Site integration | Request only | Guided embed included |
| Support | Standard | Priority |
| Audit log retention | Standard window | Extended |

**Framing for the pricing page:** lead with Core's price and the "hire a full-time employee for the price of lunch" hook; position Pro around *embedding into your own store* + *higher automation limits* + *team seats* — the things a scaling business needs. Keep yearly as the nudged default (show the discount inline).

*Open decisions:* exact conversation allowances, the Pro price point, and whether a usage-based overage or a third enterprise tier is worth adding.

---

## 17. Environment & Configuration (`.env`)

```
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash          # verify current model code before launch
DATABASE_URL=postgresql://...
JWT_SECRET=...
SMTP_HOST=...
SMTP_USER=...
SMTP_PASS=...
AUTO_REFUND_CAP=25.00                   # tune per business at onboarding
```
Never commit `.env`. Per-business overrides (refund cap, tone, thresholds) live in the DB, not the env.

---

## 18. Project Structure

*(As in the intent doc's Appendix A — `frontend/` Next.js + `backend/app/` with `agents/`, `tools/`, `guardrails/`, `handoffs/`, `rag/`, `db/`, `core/`, `schemas/`. The `tools/` package is the only place with DB access.)*

---

## 19. Observability & Cost Control

- Per-tool timing + token accounting logged to `audit_logs` / a metrics sink.
- SDK tracing routed to a **custom processor** (not OpenAI's default) since the model is Gemini.
- Caching hit-rate and escalation-rate tracked as product-health metrics.
- Success signals to watch: deflection rate, handoff-approval rate, resolution time, CSAT, cost per conversation.

---

## 20. Security & Compliance Notes

- Multi-tenant isolation enforced at the tool layer via `business_id`.
- Identity proven before account-specific reads/writes.
- Money-moving actions are gated + human-approved above the cap.
- Full audit trail; PII minimised in tool returns (scoped columns only).
- Prompt-injection screening at the input guardrail.

---

## 21. Build Phases (suggested)

1. **Foundation** — `uv` backend, FastAPI skeleton, PostgreSQL seed DB, Gemini-via-SDK model factory, one working agent + one tool end to end.
2. **The team** — orchestrator + specialists, handoffs, sessions.
3. **Safety** — input/output/tool guardrails, refund auto-cap, human approval + Decision Card.
4. **Knowledge** — doc parsing, RAG, grounding guardrail, policy checks.
5. **Comms** — SMTP themed mailer + feedback form.
6. **Frontend** — marketing pages (SEO/GEO/AEO), auth, dual dashboard.
7. **Demo** — the guided playground (§15) on seed data — the GTM centrepiece.
8. **Commercialise** — pricing (§16), integration request flow, analytics.

---

## 22. Open Decisions to Resolve

- Confirm the **current Gemini model code** + token limits, and validate its tool-calling/structured-output behaviour against the SDK early.
- Set **Pro tier price** and per-tier conversation allowances.
- Choose the **vector store** for RAG (managed vs. `pgvector` in the same PostgreSQL).
- Decide **tracing sink** (custom processor vs. disabled).
- Define the exact **refund auto-cap** default and whether it's global or per-business.

---

*This spec is deliberately implementation-flexible on the parts that change fastest (model names, SDK surface). Treat the flagged items as verify-before-build, and keep the model + provider behind a single factory so the riskiest dependency stays swappable.*