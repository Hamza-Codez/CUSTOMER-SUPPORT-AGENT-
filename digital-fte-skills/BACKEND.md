---
name: fastapi-backend-architecture
description: Build and structure the FastAPI backend for the Digital FTE Customer Support Agent with clean layering, typed contracts, and least-error controls, targeting the OpenAI Agents SDK + Gemini stack. Use when the user asks to create or edit backend endpoints, structure the FastAPI app, add a route, wire the agent runtime to HTTP, handle sessions/memory, add validation or error handling, or ensure the backend runs end to end. Covers endpoint contracts, Pydantic models, service/data separation, the tool-as-frontier rule, and testing without external dependencies.
---

# FastAPI Backend Architecture

The backend is thin and layered: routes validate and delegate, the agent runtime
reasons, the tool layer acts, the data layer persists. No business logic lives in
route handlers. Packaged with `uv`, served by `uvicorn`.

## Layering (strict)
```
app/main.py        FastAPI app + routes + request/response models (delegates only)
app/core/          config (env), auth, logging/audit
app/agents/        orchestrator + specialist agents (no HTTP concerns)
app/tools/         the DATA FRONTIER — @function_tool actions; the ONLY place with DB access
app/guardrails/    input / output / tool guardrails
app/handoffs/      human escalation + Decision Card
app/rag/           doc parsing + retrieval
app/db/            models, session, seed (PostgreSQL; mock now, same signatures for real)
app/core/model.py  provider factory: gemini_model() (mock | gemini)
app/schemas/       shared typed contracts
```
Rule: a route handler never talks to the data layer directly and never contains
policy logic. It validates input, calls the agent runtime, shapes the response.
Only `app/tools/` reads or writes PostgreSQL.

## Instructions

### Step 1: Package and run with uv + uvicorn
- `uv` manages dependencies and the venv (`pyproject.toml`, `uv sync`).
- Run the app with `uvicorn app.main:app --reload`.
- Async throughout: FastAPI async handlers + `AsyncOpenAI` client for Gemini.

### Step 2: Define the endpoint contract first
Write the Pydantic request/response before the handler.
```python
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

class AgentAction(BaseModel):
    kind: str          # "refund_prepared" | "escalated" | "order_looked_up" ...
    label: str
    ref: str | None = None

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    actions: list[AgentAction] = []
```
Typed models = automatic validation + self-documenting API. Never accept raw dicts.

### Step 3: Keep handlers thin — run the agent via the SDK Runner
```python
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, ctx: TenantContext = Depends(auth)):
    session = get_session(req.session_id, ctx.business_id)   # SDK Session
    result = await Runner.run(orchestrator, input=req.message, session=session)
    return ChatResponse(
        reply=result.final_output,
        session_id=req.session_id,
        actions=collect_actions(result),   # derive chips from tool calls
    )
```
The handler orchestrates; the Runner owns the tool loop, handoffs, and any
approval pause. The handler does not implement policy.

### Step 4: Always ship these endpoints
- `GET /health` → `{status, provider}` (liveness + which model is live).
- `POST /chat` → conversation with per-session memory.
- `GET /dashboard/escalations` → the operator queue (Decision Cards, newest first).
- `POST /escalations/{id}/decision` → approve/adjust/decline; resumes the paused run.
- `POST /onboarding/context` → seller uploads policies/catalog/tone (the context feed).
- `POST /integrations/request` → seller asks to embed the FTE.
Health first: it makes deploy and debugging deterministic.

### Step 5: Session memory
- Use the Agents SDK **Session** for conversation memory; key by `session_id` **and** `business_id`.
- A new id starts fresh memory.
- Swap interface: back the session store with PostgreSQL/Redis later; keep the same get/set calls.

### Step 6: Provider factory + config
- One `gemini_model()` factory builds the model; `MODEL_PROVIDER` selects `mock | gemini`.
- `mock` is the default so the app boots with **zero setup** (CI-safe, demo-safe).
- Gemini path: `AsyncOpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/", api_key=GEMINI_API_KEY)` wrapped in `OpenAIChatCompletionsModel(model=GEMINI_MODEL, ...)`; `set_tracing_disabled(True)` (or attach a custom trace processor) since SDK tracing targets OpenAI.
- `GEMINI_MODEL` lives in env — never hardcode the model string (names change fast).
- `CORSMiddleware` open in dev; tighten `allow_origins` for prod.
- Every environment choice via env var; never hardcode keys or URLs.

### Step 7: Auth + audit middleware (multi-tenant)
- Token-based auth resolves a `TenantContext` (`business_id`, role) on every request.
- Account-specific reads/writes prove customer identity **at the tool layer** (order_id + email match), not just at the route.
- Audit middleware / tool wrappers write every sensitive tool call to `audit_logs` (who, action, target, detail, ts).

### Step 8: Error handling (least-error)
| Case | Handling |
|---|---|
| Invalid body | Pydantic returns 422 automatically |
| Unknown provider env | `gemini_model()` raises a clear `ValueError` |
| Tool/data not-found | tool returns explicit typed result; never 500 |
| Guardrail tripwire | run stops cleanly; return a safe reply / escalate, not a 500 |
| Unexpected | let FastAPI return 500 with `{detail}`; log server-side |
Never swallow errors silently. Return a clear `detail`.

### Step 9: Test without external deps
- Run with `MODEL_PROVIDER=mock` → full flow, no API key, CI-safe.
- Unit-test tools directly against the mock store (assert `business_id` filtering).
- Test one guardrail tripwire and one human-approval pause.
- Smoke-test HTTP with `curl` on `/health`, `/chat`, `/dashboard/escalations`.

## Example
Add a "compare products" capability:
1. Contract: tool `product_catalog(query: str) -> list[ProductCard]`; no new endpoint (flows through `/chat`).
2. Handler: unchanged — the Products agent calls the tool inside the Runner loop.
3. Data: add `list_products(business_id, query)` to `db/store.py` (mock now, table later).
4. Test: `curl -X POST /chat -d '{"message":"compare A and B"}'` on `mock`.

## Troubleshooting
- **422 on valid-looking request:** field name/type mismatch. Check the Pydantic model matches the client payload.
- **Agent state lost between messages:** you created a fresh Session each call. Reuse the Session keyed by `session_id` + `business_id`.
- **CORS error in browser:** add the frontend origin to `allow_origins`.
- **Boots but every call 500s:** bad `MODEL_PROVIDER` or missing Gemini config. Check `/health`.
- **Tracing/auth errors on Gemini:** SDK tracing targets OpenAI. Disable it or route to a custom processor.
- **Logic creeping into handlers:** move it to `tools/` (actions) or `guardrails/` (policy). Handlers orchestrate only.
- **Data access outside `tools/`:** violation of the frontier rule. Move the query into a tool.
