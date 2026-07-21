# SPEC.md — Customer Support Agent (Digital FTE)

Technical source of truth. Matches the working scaffold. Every contract below is
implemented and tested on the mock provider.

---

## 1. System overview
```
Browser (Next.js)  ──HTTP/JSON──►  FastAPI  ──►  LangGraph ReAct agent  ──►  Tools ──► Store
```
- Stateless HTTP. Conversation memory keyed by `session_id` (server-side).
- Model provider chosen by env var; agent graph is provider-agnostic.
- Store is mock/in-memory now; same function interface swaps to Supabase later.

---

## 2. Repository layout
```
digital-fte/
backend/
  main.py        FastAPI app + endpoints + session memory
  agent.py       LangGraph ReAct agent (model + tools + system prompt)
  tools.py       5 tools (the agent's actions)
  store/         data layer — the only seam upstream code touches
    __init__.py    backend switch (mock | supabase) + the frozen interface
    mock_store.py  in-memory + keyword retrieval (zero-setup default)
    supabase_store.py  Postgres + pgvector, same signatures
  model.py       provider switch: mock | openai | ollama
  mock_model.py  offline rule-based tool-calling model
  embeddings.py  embedding switch: mock | openai | ollama
  db/migrations/ 0001_init.sql (schema + match_kb_docs RPC) · 0002_seed_orders.sql
                 0003_sessions.sql (conversation memory)
  scripts/       ingest_kb.py (embed + load KB) · verify_supabase.py (contract check)
  tests/         conftest · fakes · test_tools · test_api · test_store_parity ·
                 test_tools_on_supabase · test_streaming · test_sessions
  requirements.txt
  .env.example
frontend/
  app/
    layout.js    shell + nav          nav-link.js  active-route link
    page.js      streaming chat UI    session.js   localStorage session id
    tickets/page.js  ticket dashboard
    api.js       backend client (incl. SSE reader)
    globals.css  base layer + design tokens
  components/ui/ vendored shadcn primitives (button, card, badge, input, skeleton)
  lib/utils.js   cn() class merger
  tailwind.config.js · postcss.config.js · jsconfig.json
  package.json
  next.config.js
  .env.local.example
```

---

## 3. API contract (FastAPI)

### `GET /health`
Response `200`:
```json
{ "status": "ok", "provider": "mock", "data": "mock" }
```
`provider` = live model provider · `data` = live store backend (`mock | supabase`).

### `POST /chat`
Request:
```json
{ "message": "Refund ORD-1002, arrived damaged", "session_id": "web-ab12" }
```
Response `200`:
```json
{ "reply": "Refund of $329.00 approved for ORD-1002...", "session_id": "web-ab12", "provider": "mock" }
```
Rules:
- `session_id` optional, default `"default"`. New id → new memory.
- History is retained by the data layer per session and passed to the agent each call.
- Errors return standard FastAPI `4xx/5xx` with `{ "detail": "..." }`.

### `POST /chat/stream`
Same request body. Responds `text/event-stream`; each frame is `data: <json>`:
```
data: {"type": "tool",  "name": "process_refund"}
data: {"type": "token", "text": "Order "}
data: {"type": "done",  "reply": "Order ORD-1003 isn't…", "session_id": "web-ab12"}
data: {"type": "error", "detail": "The support agent is temporarily unavailable (…)"}
```
Rules:
- `tool` carries the tool **name only**; the UI maps names to chip labels. Ticket
  IDs are never parsed out of reply text.
- Only `AIMessageChunk`s become `token` frames. `stream_mode="messages"` also
  yields tool results, and forwarding those leaks internal markers like
  `[Refund policy]` into the chat.
- `done` is always the final frame, and its `reply` equals the concatenated tokens.
- **Failures arrive as an `error` frame under HTTP 200** — the status line is
  already sent by the time the agent runs. A client that only checks `res.ok`
  will miss them.
- Same agent, same guardrails as `/chat`; streaming is transport, not behaviour.

### `GET /tickets`
Response `200`:
```json
{ "tickets": [ {
  "id": "TCK-0002", "subject": "ESCALATION: needs human review",
  "detail": "...", "priority": "high", "escalated": true,
  "order_id": "ORD-1003", "status": "open", "created_at": "2026-07-20T11:49:59Z"
} ] }
```
Newest first.

---

## 4. Data models

### Order (`store.ORDERS`)
| field | type | notes |
|---|---|---|
| order_id | str | e.g. `ORD-1001` |
| customer | str | |
| items | list[str] | |
| total | float | |
| status | str | processing \| shipped \| delivered |
| carrier | str \| null | |
| tracking | str \| null | |
| eta | str (YYYY-MM-DD) | |
| refundable | bool | **enforced by process_refund** |

### Ticket (`store.TICKETS`)
| field | type | notes |
|---|---|---|
| id | str | `TCK-####`, auto |
| subject | str | |
| detail | str | |
| priority | str | low \| normal \| high |
| escalated | bool | |
| order_id | str \| null | |
| status | str | default `open` |
| created_at | str (ISO-8601 Z) | auto |

### KB doc (`kb_docs` / `mock_store.KNOWLEDGE_BASE`)
`{ title: str, body: str }` — keyword overlap on mock, pgvector cosine on Supabase.

### Store interface (frozen — both backends implement it identically)
```python
get_order(order_id: str) -> dict | None
add_ticket(subject, detail, priority="normal", escalated=False, order_id=None) -> dict
list_tickets() -> list[dict]          # newest first
search_kb(query: str) -> list[dict]   # [{title, body}], best first, [] on a miss
get_session(session_id) -> list[dict] # serialized messages, [] if new
save_session(session_id, messages) -> None
clear_session(session_id) -> None
reset_tickets() -> None               # mock only; Supabase refuses (audit log)
```
Sessions hold LangChain's `messages_to_dict` form as plain JSON; the data layer
never imports LangChain. Reads return a **deep copy** — Postgres hands back a
fresh row each query, and the mock must not let a caller mutate memory in place.
Upstream code calls `store.<fn>` only. Retrieval lives in the store, never in a
tool — `tools.search_kb` owns formatting and the escalation policy, nothing else.

**Postgres shape coercion.** PostgREST returns `numeric` as a string and
`timestamptz` with a `+00:00` offset. `supabase_store` coerces every row back to
the shapes above before returning; `tests/test_store_parity.py` enforces it.

---

## 5. Tools (the agent's actions)

| tool | signature | behaviour | writes ticket |
|---|---|---|---|
| `search_kb` | `(query: str) -> str` | top-3 KB matches by token overlap; on a miss **escalates in code** | on miss (escalated) |
| `track_order` | `(order_id: str) -> str` | order summary; asks customer to re-check if unknown | no |
| `process_refund` | `(order_id, reason) -> str` | **refunds only if `refundable`**; else refuses and **escalates in code** | yes (refund, or escalation on refusal) |
| `create_ticket` | `(subject, detail, priority='normal') -> str` | logs a follow-up | yes |
| `escalate_to_human` | `(summary, order_id='') -> str` | high-priority escalation ticket | yes (escalated) |

**Hard rule:** `process_refund` checks `order.refundable` in code. The model
cannot override it.

**Escalation is code-enforced, not model-enforced.** A refusal is never left to
the model to act on: the tool creates the high-priority `escalated` ticket itself
and returns customer-safe text the agent relays. The system prompt tells the
agent not to escalate a second time.

**Tool strings are customer-facing.** No operator instruction ("do not refund",
"ask the customer") may appear in a tool's return value — tests assert this.

---

## 6. Agent
- Built with `langgraph.prebuilt.create_react_agent(model, ALL_TOOLS, prompt=SYSTEM_PROMPT)`.
- System prompt defines the role + rules (grounded, policy, escalation).
- Loop: reason → call tool → observe → repeat → final text answer.
- Memory: full message list per session, stored in `main.SESSIONS`.

---

## 7. Model provider switch (`model.py`)
Env: `MODEL_PROVIDER = mock | openai | ollama` (default `mock`).

| provider | requires | model class |
|---|---|---|
| mock | nothing | `MockToolCallingModel` (rule-based) |

| openai | `OPENAI_API_KEY` | `ChatOpenAI` (`OPENAI_MODEL`, default gpt-4o-mini) |
| ollama | local Ollama + tool-capable model | `ChatOllama` (`OLLAMA_MODEL`, default llama3.1) |

Switching provider = env change only. No code change.

**Mock streaming is simulated.** `MockToolCallingModel._stream` computes the full
reply, then emits it word by word (`MOCK_STREAM_DELAY_MS`, default 18; tests set
0). It exists so the streaming path is demoable and testable with no API key — it
is not a claim about model latency. Real providers stream as they infer.

## 7b. Data backend switch (`store/__init__.py`)
Env: `DATA_BACKEND = mock | supabase` (default `mock`).

| backend | requires | storage | retrieval |
|---|---|---|---|
| mock | nothing | in-memory; tickets lost on restart | keyword token overlap |
| supabase | `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` | Postgres; tickets persist | pgvector cosine via `match_kb_docs` |

Read at call time, so the backend can be switched without a restart.

## 7c. Embedding switch (`embeddings.py`)
Env: `EMBEDDING_PROVIDER = mock | openai | ollama` (default `mock`),
`EMBEDDING_DIM` (default 1536, must equal `kb_docs.embedding` dims).

`mock` is a deterministic hashed bag-of-words: offline, and lexically meaningful
enough that cosine similarity behaves like keyword overlap — so the vector path
is demoable and testable with no API key. It is **not semantic**: "refund" and
"money back" are unrelated to it. Use `openai` for real retrieval.

Changing the embedding provider requires re-running `scripts/ingest_kb.py` —
vectors from one model are not comparable to queries embedded by another.

### Supabase setup (one time)
```bash
# 1. run db/migrations/0001_init.sql then 0002_seed_orders.sql in the SQL Editor
# 2. set SUPABASE_URL + SUPABASE_SERVICE_KEY in .env, DATA_BACKEND=supabase
python scripts/ingest_kb.py        # embed + load the knowledge base
python scripts/verify_supabase.py  # prove the contracts hold against your project
```

---

## 8. Frontend behaviour
Next.js App Router + Tailwind, with shadcn-style primitives vendored as source in
`components/ui/`. Design tokens live in `tailwind.config.js` and `globals.css` —
one accent, one radius scale, semantic priority colours. No ad-hoc hex per component.

- **`/` chat:** streams from `/chat/stream`; renders tokens as they arrive; shows
  a typing indicator only until the first token; action chips above each reply
  ("Processed refund", "Escalated to a human") built from `tool` frames; inline
  error on failure; Enter to send; suggestion chips; "New" resets the session.
- **`/tickets`:** polls `/tickets` every 3s; newest first; priority badge and
  escalation flag; skeletons while loading, a guiding empty state, an explicit
  error state.
- **Session id** persists in `localStorage`, so a refresh resumes the
  conversation instead of silently starting a new one.
- Backend URL via `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

---

## 9. Error handling
| case | behaviour |
|---|---|
| Unknown order id | tool asks the customer to re-check the ID; **no** ticket (a typo is not a handoff) |
| Refund on non-refundable order | tool refuses **and** writes the escalation ticket; no refund of any kind logged |
| KB has no answer | tool states it can't answer **and** writes the escalation ticket; nothing invented |
| Small talk ("hi", "thanks") | answered directly, no tool call, no ticket |
| Agent raises | `POST /chat` returns `500 {"detail": "...temporarily unavailable..."}`; internals logged server-side only; the turn is not saved, so a retry starts clean |
| Agent raises mid-stream | `POST /chat/stream` emits an `error` frame (HTTP is already 200); no `done` frame; the turn is not saved |
| Invalid request body | Pydantic returns `422` |
| Backend down | frontend shows "is the backend running on :8000?" |
| Bad provider env | `model.get_model()` raises clear `ValueError` |
| Bad `DATA_BACKEND` | `store._backend()` raises clear `ValueError` |
| `supabase` without credentials | `ValueError` naming the two missing env vars |
| Ticket insert returns no row | `RuntimeError` — the action must never be silently unlogged |
| `reset_tickets()` on Supabase | refused — the audit log is not disposable |

---

## 10. Testing methodology
- **Unit** (`test_tools.py`, 11): each tool against the mock store — policy
  branches, ticket counts, ticket shape, customer-safe strings.
- **Integration** (`test_api.py`, 15): full agent loop over HTTP on
  `MODEL_PROVIDER=mock` — no API key, CI-safe.
- **Parity** (`test_store_parity.py`, 33): the *same* assertions against both
  backends. The Supabase side runs on `tests/fakes.FakeSupabase`, which returns
  PostgREST-shaped rows (numeric as string, timestamptz with offset,
  server-generated ids) so the coercion layer is genuinely exercised.
- **Guardrails after the swap** (`test_tools_on_supabase.py`, 6): the Phase 1
  policy tests re-run unmodified on the Supabase backend.
- **Streaming** (`test_streaming.py`, 9): frame order, tokens reassembling into
  `done.reply`, parity with `/chat`, no tool output leaking as tokens, guardrails
  on the streaming path, and the mid-stream error frame.
- **Sessions** (`test_sessions.py`, 12): ownership, isolation, JSON round-trip
  with tool calls, durability across an API-module reload, and both backends.
- **Verified scenarios:** KB answer · order track · valid refund · invalid refund
  refusal · KB miss · angry-case escalation · unknown order id · ticket log
  correctness · session isolation · 500 envelope · bad provider env · bad data
  backend · missing Supabase credentials · audit-log deletion refused.
- **Manual:** `uvicorn` + `curl` for `/health`, `/chat`, `/tickets`.
- **Against a real project:** `scripts/verify_supabase.py` (needs credentials;
  not part of CI).

```bash
cd digital-fte/backend && python -m pytest tests/ -q     # 86 passed
```

---

## 11. Run
```bash
# backend
cd digital-fte/backend && pip install -r requirements.txt && cp .env.example .env
uvicorn main:app --reload --port 8000
# frontend
cd digital-fte/frontend && npm install && cp .env.local.example .env.local && npm run dev
```
Chat: http://localhost:3000 · Tickets: http://localhost:3000/tickets

---

## 12. Production swaps (interface-preserving)
| now | prod | status |
|---|---|---|
| `mock_store.KNOWLEDGE_BASE` + keyword | `kb_docs` + pgvector | **done** — `DATA_BACKEND=supabase` |
| `mock_store.ORDERS` | `orders` table | **done** — same switch |
| `mock_store.TICKETS` | `tickets` table | **done** — same switch |
| `main.SESSIONS` dict | `sessions` table | **done** — owned by `store`, same `DATA_BACKEND` switch |
| `process_refund` stub | payments/refund API | open — payments API not yet chosen |

Each swap keeps the same function signature — the agent and API don't change.