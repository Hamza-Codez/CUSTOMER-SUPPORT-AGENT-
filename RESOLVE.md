# RESOLUTION — Correction & Reshaping Spec

*Audit response for the Digital FTE platform. This is a correction spec written to be executed by Claude Code against the repo. It restates every flaw from the audit, gives the technical root cause, and specifies the fix. **Rule for the executing agent: plan each phase before coding, build the real path (not mocks), and do NOT generate exhaustive test suites — golden-path smoke checks only.***

---

## 0. Naming (locked, so nothing is ambiguous again)

| Term | What it is | State |
|---|---|---|
| **Aperture** | The platform/SaaS shell: marketing site, auth, onboarding, profile, integration manager, dashboard, demo host, billing (trial). | Reshape |
| **Demo** | An on-rails *trailer* instance shown after signup. Feels alive, but scripted. Never touches real tools/data. | Rebuild feel, isolate |
| **LIGHTRON** | The **real product**: the production agentic FTE that serves actual customers on an integrated store. No demo, no mocks, no generic replies. | Build for real |

These three are separate runtimes with separate contexts. The single biggest architectural mistake so far was letting them blur into one scripted thing.

---

## 1. The Audit — critiques, root causes, and fixes

### 1.1 "The whole thing is a puppet show — no real value, no practicality."
**Root cause (technical).** The base spec was *mock-first*. Claude Code therefore built and validated the **mock layer** end to end and stubbed the real one. `MODEL_PROVIDER=mock` was the default and nothing forced a real model + real data path to exist. The demo and the product shared one code path, so "working" meant "the script runs," not "the agent decided something."
**Fix.** Split runtimes (§0). LIGHTRON has **no mock path in its critical flow** — it runs on real models (Gemini + Groq) against real grounded data (scraped store context + live order cache). Mocks are allowed only in isolated tool unit checks, never as the shipped answer path. "Done" is redefined in §9 as *a live grounded answer on a real store*, not a passing script.

### 1.2 "The frontend is a sugar-coated wall of disguise."
**Root cause.** The UI rendered *hardcoded* strings and demo state as if they were agent output. Interfaces existed with no live data binding. It looked designed but proved nothing.
**Fix.** Every customer-facing surface binds to real runtime output (streamed tokens, tool-derived cards, real order data from the adapter). Any text that isn't grounded in tool/agent output is deleted. The dashboard shows real audit/escalation records, not placeholders. (§6, §8, §11)

### 1.3 "Tons of tests ran, but by the end it was all in vain."
**Root cause.** Mock-first + spec-driven-development pushed the agent to generate large test scaffolding that proved the mocks — high test volume, zero product value. Tests measured the wrong thing.
**Fix.** Replace volume with a **thin acceptance bar**: a handful of golden-path checks + one real end-to-end smoke against a deployed sandbox store. Explicit instruction to Claude Code: *do not write exhaustive unit suites; cap tests to the golden paths in §8.4.* (§9, §10)

### 1.4 "No real agentic hands-off with proper error boundaries — ever."
**Root cause.** The refund/escalation logic was a binary flag in a single ReAct agent; handoffs were conceptual, never wired as real Agents SDK transfers, and there was no human-approval pause. Error boundaries were `try/except → generic string`.
**Fix.** LIGHTRON uses real SDK **handoffs** (agent→agent) and a real **human-approval pause** producing a **Decision Card** (agent→human). Error boundaries are per-scenario and named *before* the happy path (§8.2, §8.5). Every gated action either executes within limits, or pauses for a human — never silently.

### 1.5 "Responses look average and don't comply with reality."
**Root cause.** Final text was templated/generic and often not grounded in real data. One model wrote both the reasoning and the prose, so the prose inherited stiff, repetitive phrasing.
**Fix.** **Two-tier model routing** (§4): Gemini reasons/decides; **Groq renders fast, natural, non-repetitive** customer prose from the decided facts. A repetition guard + tone adaptation + store persona kill the "average" feel. Grounding guardrail guarantees the words match reality. (§4, §8.6)

### 1.6 "Folder structure was fine, but the hierarchy of work and onboarding was never explained."
**Root cause.** The specs described *components* but never the **operational sequence**: who does what, in what order, from signup to a live widget.
**Fix.** §5 defines the exact onboarding hierarchy and §9 the phase order. Nothing in LIGHTRON starts before the profile is complete and a store is integrated.

---

## 2. Target architecture (reshaped, one picture)

```
                ┌───────────────────────── APERTURE (platform) ─────────────────────────┐
                │  Marketing (SSR) · Auth · Onboarding · Profile CRUD · Integrations ·   │
                │  Dashboard · Demo host · Trial billing                                 │
                └───────────────┬───────────────────────────────┬───────────────────────┘
                                │                               │
                    ┌───────────▼──────────┐        ┌───────────▼───────────────────────┐
                    │        DEMO           │        │            LIGHTRON                │
                    │ separate context      │        │  the real agentic FTE              │
                    │ scripted beats,        │        │                                    │
                    │ Groq voice (feels live)│        │  Reasoning tier:  GEMINI           │
                    │ free-type → intercept  │        │   Orchestrator→ Orders/Returns/    │
                    └────────────────────────┘        │   Products/Policy (tools+handoffs) │
                                                       │  Voice tier:      GROQ (fast NL)   │
                                                       │  Guardrails: input·ground·action   │
                                                       │  Human handoff: Decision Card      │
                                                       └───────────┬────────────────────────┘
                                                                   │ tools → DataAdapter
                                          ┌────────────────────────┴────────────────────────┐
                                          │  Flavour A: LocalScrapeAdapter (BUILD NOW)        │
                                          │   scraped static KB + browser ephemeral cache     │
                                          │  Flavour B: StoreApiAdapter (COMING SOON)         │
                                          │   authenticated server-side store API             │
                                          └───────────────────────────────────────────────────┘
```

**The rule that makes this maintainable:** LIGHTRON's tools never know which flavour is live. They call a `DataAdapter` interface. Flavour A and B are two implementations of the same interface — swapping them is a data-source change, not a rewrite (§7).

---

## 3. Two flavours

### Flavour A — Frontend-scrape mode (BUILD NOW)
The seller pastes their store URL; Aperture scrapes it and injects a **real working LIGHTRON widget** into that store's frontend. No store backend required.

- **Two kinds of data:**
  1. **Static context** (policies, refund policy, shipping, FAQ, product info): scraped + parsed into a **per-store knowledge base** at integration time. Non-user-specific. This is the grounding source.
  2. **Ephemeral order cache** (in-cart, in-delivery, delivered, etc.): collectable **only while the customer is on the store site**. The widget reads what's visible to the browser and caches it in **local storage**. Sent as ephemeral context per query.
- **Answering:** LIGHTRON grounds each reply in (a) the retrieved static KB + (b) the realtime injected page/cart/order context. No invented answers.
- **Privacy:** only on opt-in stores (the seller integrates their own site). The ephemeral cache is client-side and session-scoped; the widget states what it reads.

### Flavour B — Full API mode (COMING SOON)
Fully built stores expose an authenticated orders/customers API; `StoreApiAdapter` gives LIGHTRON real server-side reads/writes. **Design the adapter interface now so B is a drop-in later.** Keep it visibly "coming soon" in the UI.

---

## 4. Model routing — Gemini (brain) + Groq (voice)

Both are OpenAI-compatible, so both use the same SDK pattern (`AsyncOpenAI` → `OpenAIChatCompletionsModel`, never a bare string; tracing disabled for non-OpenAI providers).

| Tier | Provider | Role | Endpoint | Env |
|---|---|---|---|---|
| **Reasoning / Orchestration** | **Gemini** | triage, tool selection, handoff decisions, guardrail judgments | `https://generativelanguage.googleapis.com/v1beta/openai/` | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| **Voice / Response** | **Groq** | render the decided answer as fast, natural, non-generic prose (streamed) | `https://api.groq.com/openai/v1` | `GROQ_API_KEY`, `GROQ_MODEL` |

```python
# core/model.py — two factories, one pattern
def gemini_model():   # reasoning tier
    c = AsyncOpenAI(api_key=os.environ["GEMINI_API_KEY"],
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    set_tracing_disabled(True)
    return OpenAIChatCompletionsModel(model=os.environ["GEMINI_MODEL"], openai_client=c)

def groq_model():     # voice tier
    c = AsyncOpenAI(api_key=os.environ["GROQ_API_KEY"],
                    base_url="https://api.groq.com/openai/v1")
    set_tracing_disabled(True)
    return OpenAIChatCompletionsModel(model=os.environ["GROQ_MODEL"], openai_client=c)
```

**Flags (verify before build):**
- **Groq model IDs churn.** Groq has deprecated its Llama chat models; use current IDs (e.g. `openai/gpt-oss-120b` / `gpt-oss-20b`) and keep the ID in `GROQ_MODEL`. Check Groq's models page.
- Keep tool-calling/agentic reasoning on **Gemini**; keep Groq for prose only (reasoning-model JSON/tool-call formats on Groq have constraints — avoid them by not tool-calling there).
- **Latency win, one extra hop.** Mitigate: stream Groq output; skip the voice tier entirely for deterministic UI cards (order lists, summaries) — render those directly from tool data (§8.6).

---

## 5. Onboarding & profile hierarchy (the missing sequence)

Exact order. LIGHTRON service is gated behind a complete profile.

1. **Sign up** — email + password + **username** (store username at signup).
2. **Complete your profile** (mandatory gate before any FTE service). Collect:
   - WhatsApp number
   - Store name
   - Store URL (to integrate)
   - Strict policies & mandate (this becomes LIGHTRON's policy + brand-voice source)
3. **Free-month trial auto-applied** — no pricing prompt during onboarding. Pricing is unchanged, just deferred; show trial status, not a paywall.
4. **Choose flavour** — A (available) or B (coming soon).
5. **Integrate** — Aperture scrapes the store URL, builds the per-store KB, issues the widget embed snippet.
6. **Demo available** — as a post-signup trailer (separate from LIGHTRON).
7. **Account management** — user can **update and delete** profile fields, and **delete the account** (full data delete). One-time entry, full ownership thereafter.

**Data model additions:** `users(id, email, pw_hash, username, created)`, `profiles(user_id, whatsapp, store_name, store_url, policies_text, brand_voice, status)`, `subscriptions(user_id, plan, trial_ends)`, `integrations(user_id, flavour, kb_id, widget_key, scraped_at)`.

---

## 6. Flavour A architecture (Python, agentic) — BUILD NOW

### 6.1 Integration-time ingestion (runs once per store, re-runnable)
```
scrape(store_url)                     # Playwright for JS sites; httpx+selectolax for static
  → discover key pages               # policies, refund, shipping, returns, FAQ, product pages
  → parse to clean text + metadata    # page_type, url
  → chunk + embed                     # per-store vector KB, keyed by store_id (pgvector or lite store)
  → extract policies + brand_voice → profile
```
Store the KB id on `integrations`. Grounding retrieval (`policy_retriever`) reads only this store's namespace.

### 6.2 Runtime widget (injected into the store frontend)
- Embed: `<script src="https://cdn.aperture.../lightron.js" data-store="STORE_KEY"></script>`
- The widget:
  - captures on-page context (current product, cart, visible order status) → **ephemeral_context**
  - maintains the **order cache** in `localStorage` (in-cart / in-delivery / delivered), updated as the customer browses
  - `POST /widget/chat {store_key, message, ephemeral_context}` to Aperture → streamed LIGHTRON reply
- **No source-of-truth in the widget.** It ships ephemeral context up; LIGHTRON decides.

### 6.3 The adapter that makes this real
`LocalScrapeAdapter` implements `DataAdapter` (§7) by reading: static answers from the scraped KB, order/cart facts from the request's `ephemeral_context`. When a real order isn't visible to the browser, the adapter returns "not-visible" → LIGHTRON asks the customer or escalates (never invents).

---

## 7. The DataAdapter contract (why Flavour B is not a rewrite)

```python
class DataAdapter(Protocol):
    async def get_orders(self, ctx) -> list[Order]: ...
    async def get_order(self, ctx, order_id: str) -> Order | None: ...
    async def get_cart(self, ctx) -> Cart | None: ...
    async def search_policies(self, ctx, query: str) -> list[Passage]:   # returns source_ref
    async def search_products(self, ctx, query: str) -> list[Product]: ...
    async def create_return(self, ctx, order_id, reason) -> ActionResult:  # gated
    async def create_refund(self, ctx, order_id, amount, reason) -> ActionResult:  # gated
```
- Flavour A → `LocalScrapeAdapter` (KB + ephemeral context; write-actions produce Decision Cards, since there's no store backend to execute against).
- Flavour B → `StoreApiAdapter` (authenticated store API; write-actions can execute within policy).
- **LIGHTRON's tools call the adapter, not a data source.** Switching flavour swaps one binding.

---

## 8. LIGHTRON — the real FTE (the core of this project)

### 8.1 Information flow (end to end, no mocks)
```
customer msg + ephemeral_context
  → Aperture API (auth store_key, load session)
  → Orchestrator (GEMINI) triage → route to specialist
  → Specialist (GEMINI) selects tools → tools call DataAdapter → grounded facts + decision
  → [if gated/over-policy] pause → Decision Card → human approval → resume
  → Voice (GROQ) renders natural reply from {intent, facts, decision, tone, store persona}
  → guardrails (grounding, tone, action) → stream to widget
  → audit log written
```

### 8.2 Scenario map (build this BEFORE coding responses)
Each scenario is a row: trigger → info needed → tools → decision → boundary/handoff → response shape. This is the contract the agents implement.

| Scenario | Trigger | Info needed | Tools | Decision logic | Boundary / handoff | Response shape |
|---|---|---|---|---|---|---|
| Order status | "where's my order" | order id / from cache | get_order | found→status; missing→ask | not-visible→ask/escalate | status card + ETA |
| Order list | "my orders" | cache/adapter | get_orders | list, newest first | none | **clickable list → summary** |
| Delayed delivery | past-ETA order | order + policy | get_order, search_policies | compare ETA vs now; cite policy | severe delay→escalate | empathetic + next step |
| Wrong item received | "got wrong item" | order + return policy | get_order, search_policies, create_return | eligible?→open return | dispute→Decision Card | return steps + ref |
| Change of mind (pre-dispatch) | cancel request | order status | get_order | if not dispatched→cancel path | dispatched→returns path | outcome + options |
| Return (post-delivery) | "return this" | order + window | get_order, search_policies, create_return | within window?→return | edge/out-of-policy→Decision Card | eligibility + label steps |
| Replace | "replace defective" | order + policy | get_order, search_policies, create_return | defect + in-window→replace | stock issue→escalate | replacement plan |
| Refund | "refund me" | order + policy + cap | get_order, search_policies, create_refund | in-policy AND ≤ cap→prepare | over-cap/out-of-policy→**human approval** | ruling, warmly |
| T&C-based answer | policy question | KB | search_policies | ground in passage | no source→escalate | grounded answer + ref |
| Angry / tone | sentiment negative | message | (classify) | adapt register, prioritize | legal/threat→escalate high | de-escalating, human |
| Connection drop mid-chat | reconnect | session | (session) | resume from last state | none | "picking up where we left off" |
| Evaluate → decide | ambiguous ask | context | multiple | gather → reason → act | low confidence→ask/escalate | decision + rationale |
| Decide on behalf | "you choose" | order + policy | multiple | pick best in-policy option | irreversible→confirm/approve | proposed action + confirm |
| Summary organizer | "summarize my case" | conversation + orders | get_orders | assemble structured summary | none | organized summary card |
| Out of scope | off-topic | — | — | refuse politely, redirect | — | scope redirect |

### 8.3 Agentic handoffs
- **Agent→agent:** SDK `handoff()` — Orchestrator→specialist; specialist→specialist (Orders→Returns). History carries over.
- **Agent→human:** gated/over-policy/angry/low-confidence → **Decision Card** (verified customer, request, policy check, proposed action, Approve/Adjust/Decline). Run pauses; operator's click resumes it; outcome returns to the same chat. In Flavour A (no store backend) **all write-actions become Decision Cards** by design.

### 8.4 Guardrails (real, testable — these ARE the golden paths)
- **Input:** scope (in-domain?), injection/abuse screen.
- **Grounding (output):** any policy/product/order claim must carry a `source_ref` from the adapter/KB; missing → trip → ask or escalate. No invention.
- **Action (tool):** identity verified; refund ≤ `AUTO_REFUND_CAP`; else pause for human. Runs on every tool call, even inside a handoff chain.
- **Tone/repetition (voice):** see §8.6.

Golden-path smoke set (the ONLY tests to write): order-status found/not-visible; return in-window/out-of-window→Decision Card; refund in-cap/over-cap→approval; KB-miss→escalate; angry→escalate; reconnect resumes.

### 8.5 Error boundaries (named before happy path)
Adapter returns typed outcomes (`found | not_visible | not_eligible | needs_human`), never exceptions-as-answers. The Voice tier never fabricates to fill a gap — an empty/negative adapter result routes to *ask the customer* or *escalate*.

### 8.6 Non-generic response methodology (kills the "average" feel)
- **Structured cards render from data, not prose** — order lists, summaries, status use UI components fed by tool output (fast, exact, never generic). The Voice tier handles only conversational glue.
- **Voice inputs:** `{intent, grounded_facts, decision, customer_tone, store_persona}`. Groq is instructed to vary phrasing, match the store's brand voice, and never use filler.
- **Repetition guard:** keep the last N assistant phrasings per session; if the new reply is too similar, re-render.
- **Tone adaptation:** detect calm/frustrated/confused and shift register accordingly.
- **Persona:** greet and speak as *{store_name}'s* assistant, grounded in the profile's policies/mandate.

---

## 9. Demo mode (trailer that feels alive)

- **Separate context and runtime** — its own seeded orders, its own path; never calls LIGHTRON tools/data.
- **Greeting** uses the signed-in **username + store name**: e.g. "Hi {username} — here's how {store_name}'s FTE handles a real day."
- Shows **demo orders with transit stages**; guided by clickable steps (rest as now).
- **Feels alive:** render the scripted beats through the **Groq voice tier** so phrasing is natural, not canned — but strictly on-rails.
- **Free-type intercept (demo guardrail):** if the user types manually instead of following the guided clicks → "This is a demo — see LIGHTRON working live on your store" → CTA/navigate to the **Integrations** page.

---

## 10. Repo restructure (what Claude Code changes)

```
backend/app/
  core/           [EDIT]  config, auth, logging; model.py → gemini_model() + groq_model()
  onboarding/     [NEW]   signup, profile gate, trial, account CRUD/delete
  scrape/         [NEW]   crawler + parser + embedder (Flavour A ingestion)
  adapters/       [NEW]   DataAdapter protocol; LocalScrapeAdapter; StoreApiAdapter (stub)
  agents/         [EDIT]  orchestrator + Orders/Returns/Products/Policy (Gemini)
  voice/          [NEW]   Groq response renderer + repetition/tone guards
  tools/          [EDIT]  call DataAdapter only (the frontier)
  guardrails/     [EDIT]  input, grounding, action
  handoffs/       [EDIT]  Decision Card + human approval pause
  demo/           [NEW]   isolated demo context, seed, free-type intercept
  scenarios/      [NEW]   scenario map configs (§8.2) the agents implement
  db/             [EDIT]  users, profiles, subscriptions, integrations, orders, escalations, audit
frontend/
  app/(marketing) [KEEP]  restyle only; bind real data
  app/onboarding  [NEW]   signup → profile → integrate
  app/demo        [EDIT]  greeting by name/store; Groq-rendered beats; intercept
  app/dashboard   [EDIT]  real escalation queue + audit (no placeholders)
  widget/         [NEW]   embeddable lightron.js (ephemeral context + localStorage cache)
DEPRECATE:               scripted "demo == product" path; mock-as-shipped-answer; bulk test scaffolding
```

---

## 11. Deployment & "real results" acceptance

- **Widget cross-origin:** serve `lightron.js` from a CDN; backend CORS allows the store origins; `store_key` scopes each request to a tenant KB.
- **Hosting:** backend on a real host (uvicorn workers), managed PostgreSQL, secrets via env, `/health` returns live providers.
- **Acceptance = a live grounded conversation**, not test volume:
  1. Sign up → complete profile → integrate a real sample store (scrape succeeds, KB built).
  2. Widget loads on that store; ask 5 scenarios from §8.2 → answers are grounded, non-generic, and correct.
  3. One out-of-policy refund → Decision Card appears in the dashboard → operator approves → reply returns to chat.
  4. Demo greets by name, runs on rails, intercepts free-typing.
  5. Deployed URL works (not just localhost).
- **Instruction to the executing agent:** plan each phase, build the real path, keep tests to the golden-path smoke set in §8.4. No long iterative test runs.

---

## 12. Open decisions (need your call)

- **Vector store for the per-store KB:** `pgvector` in the same PostgreSQL (simplest) vs a managed store. Recommend pgvector for now.
- **Scraper engine default:** Playwright (handles JS stores, heavier) vs static-first with Playwright fallback. Recommend static-first + fallback.
- **Groq model ID** (current, from Groq's models page) and **Gemini model ID** — both into env.
- **Auto-refund cap** default for Flavour A (where actions are Decision Cards anyway) — likely 0, so everything is human-approved until Flavour B.
- Confirm **"Aperture"** as the platform name and **"LIGHTRON"** as the product name for all UI copy.

---

*Bottom line: the previous build proved a script. This spec builds a product — LIGHTRON, grounded on a real store's scraped context and live order cache, reasoning on Gemini, speaking through Groq, handing off to a human when it should, and deployed so a real customer gets a real answer. Build that path first; keep the demo as an honest trailer beside it.*