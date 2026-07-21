---
name: fastapi-backend-architecture
description: Build and structure the FastAPI backend for the Digital FTE Customer Support Agent with clean layering, typed contracts, and least-error controls. Use when the user asks to create or edit backend endpoints, structure the FastAPI app, add a route, wire the agent to HTTP, handle sessions/memory, add validation or error handling, or ensure the backend runs end to end. Covers endpoint contracts, Pydantic models, service/data separation, and testing without external dependencies.
---

# FastAPI Backend Architecture

The backend is thin and layered: routes validate and delegate, the agent layer
reasons, the data layer persists. No business logic lives in route handlers.

## Layering (strict)
```
main.py    routes + request/response models + session memory (delegates only)
agent.py   agent construction (no HTTP concerns)
tools.py   actions (no HTTP, no framework)
store.py   data access (mock now; same signatures for real)
model.py   provider switch (mock | openai | ollama)
```
Rule: a route handler never talks to the data layer directly and never contains
policy logic. It validates input, calls the agent/service, shapes the response.

## Instructions

### Step 1: Define the endpoint contract first
Write the Pydantic request/response before the handler.
```python
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    provider: str
```
Typed models = automatic validation + self-documenting API. Never accept raw dicts.

### Step 2: Keep handlers thin
```python
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    history = SESSIONS.setdefault(req.session_id, [])
    history.append(HumanMessage(content=req.message))
    result = get_agent().invoke({"messages": history})
    SESSIONS[req.session_id] = result["messages"]
    reply = last_ai_text(result["messages"])
    return ChatResponse(reply=reply, session_id=req.session_id,
                        provider=os.getenv("MODEL_PROVIDER", "mock"))
```
The handler orchestrates; it does not implement.

### Step 3: Always ship these three endpoints
- `GET /health` -> `{status, provider}` (liveness + which model is live).
- `POST /chat` -> conversation with per-session memory.
- `GET /tickets` -> the agent's audit log (newest first).
Health first: it makes deploy and debugging deterministic.

### Step 4: Session memory
- Key by `session_id`; store the full message list per session.
- Default id `"default"`; a new id starts fresh memory.
- Interface for swap: replace the `SESSIONS` dict with a store module later; keep the same get/set calls.

### Step 5: CORS + config
- `CORSMiddleware` open in dev; tighten `allow_origins` for prod.
- Every environment choice via env var; never hardcode keys or URLs.
- Provider read from `MODEL_PROVIDER`; default `mock` so it boots with zero setup.

### Step 6: Error handling (least-error)
| Case | Handling |
|---|---|
| Invalid body | Pydantic returns 422 automatically |
| Unknown provider env | `get_model()` raises clear `ValueError` |
| Tool/data not-found | tool returns explicit text; never 500 |
| Unexpected | let FastAPI return 500 with `{detail}`; log server-side |
Never swallow errors silently. Return a clear `detail`.

### Step 7: Test without external deps
- Run with `MODEL_PROVIDER=mock` -> full flow, no API key, CI-safe.
- Unit-test tools directly against the mock store.
- Smoke-test HTTP with `curl` on `/health`, `/chat`, `/tickets`.

## Example
Add a "list orders" endpoint:
1. Contract: `GET /orders -> {orders: [...]}`.
2. Handler: calls `store.list_orders()`, returns shaped response. No logic inline.
3. Data: add `list_orders()` to `store.py` (mock now, table later).
4. Test: `curl localhost:8000/orders`.

## Troubleshooting
- **422 on valid-looking request:** field name/type mismatch. Check the Pydantic model matches the client payload.
- **Agent state lost between messages:** you overwrote `SESSIONS[session_id]` with a fresh list. Append to existing history, then store the returned messages.
- **CORS error in browser:** add the frontend origin to `allow_origins`.
- **Boots but every call 500s:** bad `MODEL_PROVIDER` or missing provider package. Check `/health`; install the provider extra.
- **Logic creeping into handlers:** move it to `tools.py`/`store.py`. Handlers orchestrate only.
