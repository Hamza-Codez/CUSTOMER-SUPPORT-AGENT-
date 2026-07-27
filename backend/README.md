# Digital FTE — Backend

FastAPI backend running the **OpenAI Agents SDK** against **Gemini**, with
PostgreSQL behind a typed tool layer.

Built against [`../SPEC.md`](../SPEC.md); see [`../INTENT.md`](../INTENT.md) for the product intent.

---

## Run it

The app boots with **zero setup** — no API key, no database:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

```bash
curl localhost:8000/health
# {"status":"ok","provider":"mock","store":"mock","db":"up"}

curl -X POST localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer demo-token' \
  -d '{"message":"where is ORD-1002? email ayesha.k@example.com"}'
```

## Tests

```bash
uv run pytest          # 43 pass, no API key or database required
```

The Postgres suite (`tests/test_postgres.py`) skips itself unless a real
`DATABASE_URL` is set, and runs the same assertions the in-memory store passes.

## Configuration

Copy `.env.example` to `.env` and fill in what you need. `.env` is gitignored.

| Variable | Effect |
|---|---|
| `MODEL_PROVIDER` | `mock` (default, no key needed) or `gemini` |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | required when `MODEL_PROVIDER=gemini` |
| `DATABASE_URL` | empty → in-memory store; a DSN → PostgreSQL |
| `DEV_TOKENS` | `<token>:<business_id>:<role>`, comma separated |

Two independent switches: the model provider and the store. Any combination
works, so you can point real Gemini at the in-memory store or vice versa.

### Going real

> **URL-encode the password in `DATABASE_URL`.** A raw `#` truncates the URL into
> a fragment and the port parses as garbage (`invalid literal for int()`).
> `#`→`%23`, `/`→`%2F`, `*`→`%2A`, `@`→`%40`, `:`→`%3A`.

> **Our tables live in an `fte` schema, not `public`.** The database this was
> built against already hosted unrelated projects with colliding table names
> (`orders`, `products`, `users`); `create table if not exists` would have bound
> to those. Namespacing keeps us additive — nothing outside `fte` is touched.

```bash
# 1. Put a DATABASE_URL in .env, then create the schema and demo rows:
uv run python scripts/init_db.py

# 2. Confirm the Postgres path actually works:
uv run pytest tests/test_postgres.py -v

# 3. Switch the model on: MODEL_PROVIDER=gemini + GEMINI_API_KEY in .env
uv run uvicorn app.main:app --reload
curl localhost:8000/health   # -> "provider":"gemini","store":"postgres"
```

---

## Layout

```
app/
  main.py          FastAPI: /health, /chat. Delegates only — no policy, no SQL.
  core/
    config.py      env loading; every environment choice is a variable
    model.py       gemini_model() — the one place a model is constructed
    mock_model.py  a real Model impl; drives the true Runner loop without an API key
    auth.py        token -> TenantContext(business_id, role)
    audit.py       audit log writer
  agents/
    orchestrator.py  triage + the whole team wired together; get_entry_agent()
    orders.py        identity check + order status
    support.py       grounded policy answers
    products.py      explanations and comparisons
    refunds.py       policy check + eligibility (no money-moving tool yet — Phase 3)
  tools/           THE ONLY DOOR TO DATA
    orders.py        order_lookup
    products.py      product_catalog
    policies.py      policy_retriever
  rag/
    keyword.py     IDF-weighted keyword retrieval; the Phase 4 vector-store swap point
  db/
    base.py        the Store contract both implementations satisfy
    mock_store.py  in-memory; mirrors seed.sql
    postgres_store.py
    session_store.py  SessionABC impl (see note below)
    schema.sql / seed.sql
  schemas/         frozen typed contracts shared by HTTP and tools
```

### The rules this layout enforces

- **Tools are the frontier.** Only `app/tools/` touches the data layer. The model
  never sees SQL and never receives a row it did not ask for through a tool.
- **Tenancy is not a parameter.** `business_id` comes from the caller's token via
  the run context, never from a tool argument — so a model cannot name the tenant
  it reads from, whatever it is persuaded to say.
- **Failures are typed values.** A missing order or a failed identity check is a
  normal result the agent reasons about, not an exception that becomes a 500.
- **Refusals are logged too.** A denied identity check is exactly the event worth
  having on record.
- **A retrieval miss returns nothing.** Retrieval that always returns something
  can never miss, so the agent never learns it doesn't know — it just cites
  whatever was least unrelated. `keyword.MIN_RELEVANCE` is what makes "I can't
  confirm that" reachable.
- **Money-moving tools arrive already gated.** The Refunds agent deliberately has
  no `refund_processor` in this phase. It lands in Phase 3 together with its cap,
  tool guardrail and approval pause — never in an ungated state, not even briefly.

---

## Verified

Checked against the real thing on 2026-07-26, not assumed:

| What | Result |
|---|---|
| `openai-agents` 0.18.3 on Python 3.14.3 | works |
| **119 tests**, mock and PostgreSQL, no skips | pass |
| Live `uvicorn` — `/health`, `/chat`, 401, multi-turn memory | pass |
| **Gemini tool-calling** via the OpenAI-compatible endpoint | **confirmed** |
| **Gemini handoffs** — Orchestrator → Orders → `order_lookup`, → Support → cited policy | **confirmed** |
| Gemini honours identity refusal, unknown order, prompt injection | no data leaked |
| Cross-tenant attempt (naming another `business_id` in a message) | structurally ignored |
| **Real Supabase PostgreSQL** — schema, seed, tools, audit, sessions | pass |
| Mock and Postgres stores return identical records | asserted per-row |
| Full stack: real Gemini reading real Postgres | pass, audit persisted across processes |

**Not verified against real Gemini yet:** routing to Products and Refunds, and
the grounding-refusal and injection cases *in the multi-agent setup*. All are
covered on the mock provider — which drives the real Runner, real handoffs and
real tools — but the mock cannot prove the live model's judgement. Verification
stopped because the free-tier **daily** quota ran out mid-run; see below.

⚠️ **`gemini-2.5-flash` does not work on new API keys.** It is still returned by
the models endpoint, but calling it 404s with *"no longer available to new users"*.
A pinned model name is therefore not automatically the safer choice on Gemini —
re-verify whatever you pin.

### ⚠️ Free-tier quota is a product constraint, not just a dev annoyance

`gemini-flash-latest` currently resolves to **`gemini-3.6-flash`**, whose free
tier allows **20 requests per day** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`),
alongside a 5/minute limit. Failed requests count against both.

This design costs **two model calls per customer turn** — one for the Orchestrator
to route, one for the specialist — which is the price of specialisation. On the
free tier that is roughly **10 conversation turns per day**. The demo playground
in Phase 7 is not viable on that, so either a paid key or a model with a larger
free allowance is needed before then. Worth deciding early rather than at demo time.

⚠️ **`gemini-2.5-flash` does not work on new API keys.** It is still returned by
the models endpoint, but calling it 404s with *"no longer available to new users"*.
A pinned model name is therefore not automatically the safer choice on Gemini —
re-verify whatever you pin.

## Notes for the next phase

- **`SQLiteSession` does not exist in openai-agents 0.18.3.** `Session` is an ABC
  (`get_items` / `add_items` / `pop_item` / `clear_session`), so conversation
  memory is ours: see `db/session_store.py`.
- **Tool results are stringified with `str()` before the model sees them.** For a
  Pydantic model that yields Python repr, which wastes tokens and is awkward to
  parse. `OrderLookupResult.__str__` emits compact JSON instead — any new tool
  result type should do the same.
- **Human approval is already available in the SDK** and is what Phase 3's
  Decision Card will use: `function_tool(needs_approval=...)` →
  `RunResult.interruptions` → `RunState.to_json()` / `from_json()` →
  `.approve()` / `.reject()` → `Runner.run(agent, state)`. The state serialises,
  so an operator can approve in a later request.
- **`get_entry_agent()` is the swap point.** Phase 2 repoints it from the Orders
  agent to the Orchestrator; no HTTP or tool contract changes.
