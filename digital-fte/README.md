# Digital FTE — Customer Support Agent

A minimal but fully operational, end-to-end AI **Customer Support Agent** that
replaces a Tier-1 support executive. It answers FAQs, tracks orders, processes
in-policy refunds, opens tickets, and escalates complex issues — logging every
action to a live dashboard.

```
Next.js (chat + ticket dashboard)  ──►  FastAPI  ──►  LangGraph ReAct agent
                                                          │
                                          tools: search_kb · track_order ·
                                                 process_refund · create_ticket ·
                                                 escalate_to_human
                                                          │
                                          mock in-memory store (swap for
                                          Supabase + Pinecone/pgvector)
```

## Why it's an FTE, not a chatbot
It has **tools** (it takes real actions), **memory** (per-session history), and an
**audit trail** (every action becomes a ticket), plus **human-in-the-loop
escalation**. That's a role, not a Q&A box.

## Runs with ZERO setup
The default model provider is `mock` — a rule-based tool-calling model — so the
whole system runs end-to-end with **no API key and no model install**. Swap in a
real LLM whenever you want (see below).

---

## Quick start

### 1. Backend (terminal 1)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
cp .env.example .env            # MODEL_PROVIDER=mock by default
uvicorn main:app --reload --port 8000
```
Check: http://localhost:8000/health

### 2. Frontend (terminal 2)
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```
Open http://localhost:3000 — chat on `/`, tickets on `/tickets`.

---

## Try it
In the chat, send:
- `How long does shipping take?` → answers from the knowledge base (RAG stand-in)
- `Track ORD-1001` → looks up the order
- `Refund ORD-1002, arrived damaged` → processes refund + logs a ticket
- `Refund ORD-1003` → refuses (not refundable) and flags for escalation
- `This is unacceptable, I want a manager` → escalates to a human (high-priority ticket)

Watch the **Tickets** tab update live as the agent works.

---

## Switching to a real model

Edit `backend/.env`:

**OpenAI**
```
MODEL_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```
Then `pip install langchain-openai`.

**Ollama (local & free)**
```
MODEL_PROVIDER=ollama
OLLAMA_MODEL=llama3.1     # use a tool-calling capable model
```
Then `ollama pull llama3.1` and `pip install langchain-ollama`.

No other code changes needed — the agent graph is model-agnostic.

---

## Going to production (swap the mocks)
| Mock (here) | Production |
|---|---|
| `store.KNOWLEDGE_BASE` + keyword search | Pinecone or pgvector similarity search |
| `store.ORDERS` dict | Supabase / your orders API |
| `store.TICKETS` list | Supabase table |
| `SESSIONS` dict in `main.py` | Supabase / Redis for durable memory |
| `process_refund` mock | real payments/refund API |

## Deploy
- **Frontend:** push `frontend/` to Vercel; set `NEXT_PUBLIC_API_URL` to your backend URL.
- **Backend:** deploy `backend/` to Render / Railway / Fly.io (free tier).

## Layout
```
backend/   FastAPI + LangGraph agent, tools, model switch, mock store
frontend/  Next.js App Router: chat page + tickets dashboard
```
