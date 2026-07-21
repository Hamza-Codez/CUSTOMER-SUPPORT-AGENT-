# Customer Support Agent — a Digital FTE

A Tier-1 customer support agent that answers from a knowledge base, tracks
orders, processes refunds **within policy only**, and escalates everything else
to a human — with every action written to an auditable ticket log.

It is not a chatbot. It has the four traits that make it an FTE: a **role**,
real **tools**, per-user **memory**, and **accountability** for every action.

---

## Run it (60 seconds, no accounts, no API keys)

```bash
# 1. backend  →  http://localhost:8000
cd digital-fte/backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
cp .env.example .env
.venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000

# 2. frontend →  http://localhost:3000   (second terminal)
cd digital-fte/frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000, click **Continue as a support agent**, and try the
suggestion chips. No database, no model API key, no signup — every provider
defaults to a working local mock.

## The 90-second demo

1. **Sign in as a support agent.**
2. *"How long does shipping take?"* → grounded answer from the knowledge base.
3. *"Track ORD-…"* (use a chip) → order status, streamed token by token.
4. *"Refund ORD-…, arrived damaged"* → **approved**, ticket logged.
5. *"Refund ORD-…"* (the processing one) → **refused and escalated** — the model
   cannot talk past it, the check is in code.
6. *"do you offer gift wrapping"* → *"no article covers that"* → escalated.
   It never invents an answer.
7. **Tickets** tab → every action above, newest first, with priority and
   escalation flags.
8. Sign out, sign back in as a **customer**, open Tickets → **refused**. The
   audit log is agent-only.

## What runs where

```
Next.js (chat + audit dashboard, Tailwind)
      │  HTTP + Authorization: Bearer <token>
Auth  │  verify session · roles: customer | agent
      ▼
FastAPI (orchestration, per-user memory, logging)
      ▼
LangGraph ReAct agent ──► search_kb · track_order · process_refund
                          create_ticket · escalate_to_human
      ▼
Data layer  (mock in-memory  ⇄  Supabase + pgvector)
```

Three independent switches, all defaulting to a zero-setup mock:

| Switch | Options | What it changes |
|---|---|---|
| `MODEL_PROVIDER` | `mock` · `openai` · `ollama` | Which LLM reasons |
| `DATA_BACKEND` | `mock` · `supabase` | Where orders, tickets, KB and sessions live |
| `AUTH_PROVIDER` | `mock` · `supabase` | How identity is verified |

Going to production is a config change, not a rewrite: every backend implements
the same frozen `store.*` contracts, and the same tests run against both.

## The rules it cannot break

- **Refund policy is enforced in code, never in the prompt.** A non-refundable
  order is refused *and* escalated by the tool itself.
- **Grounded or escalate.** A knowledge-base miss says so and hands off. No
  invented policy.
- **Every state change writes a ticket.** Nothing happens silently.
- **Every state-changing endpoint requires a valid session**; the audit log is
  restricted to agents; customers cannot see each other's orders.

## Tests

```bash
cd digital-fte/backend && .venv/Scripts/python.exe -m pytest tests/ -q
```

163 tests, all on the mock providers — no API key, no database, CI-safe. They
cover the guardrails (both refund paths, KB miss, escalation), the streaming
contract, per-user isolation, auth 401/403, and **run the same assertions
against both the mock and Supabase backends**.

## Going live

**Database + real retrieval** — create a Supabase project, then:
```bash
# paste digital-fte/backend/db/schema.sql into the Supabase SQL Editor, run once
cd digital-fte/backend
# put SUPABASE_URL + SUPABASE_SERVICE_KEY in .env, set DATA_BACKEND=supabase
.venv/Scripts/python.exe scripts/ingest_kb.py        # embed + load the KB
.venv/Scripts/python.exe scripts/verify_supabase.py  # prove the contracts hold
```

**Real auth** — set `AUTH_PROVIDER=supabase` plus `SUPABASE_JWT_SECRET`
(Project Settings → API → JWT Secret), and on the frontend
`NEXT_PUBLIC_AUTH_PROVIDER=supabase` with the URL and **anon** key. Grant an
agent their role in Supabase with `app_metadata.role = "agent"` —
`user_metadata` is user-editable and is deliberately ignored.

**Real model** — `MODEL_PROVIDER=openai` + `OPENAI_API_KEY`, or run Ollama
locally with a tool-capable model.

**Deploy** — `digital-fte/render.yaml` (backend) and
`digital-fte/frontend/vercel.json` (frontend). Set `ALLOWED_ORIGINS` on Render
to your Vercel URL, and `NEXT_PUBLIC_API_URL` on Vercel to your Render URL.

## Documents

| File | Answers |
|---|---|
| [INTENT.md](INTENT.md) | Why this exists, the four FTE traits, non-negotiables |
| [PRD.md](PRD.md) | Problem, success metrics, scope by phase |
| [SPEC.md](SPEC.md) | Contracts, data models, tool signatures, error handling |

## Known limits

- The refund tool is a **stub** — it logs and replies, but moves no money. A
  payments provider hasn't been chosen.
- The **mock embedder is lexical, not semantic**: it matches words, not meaning.
  Good enough to demo the vector path offline; use `EMBEDDING_PROVIDER=openai`
  for real retrieval.
- Mock streaming is **simulated** — the reply is computed, then emitted word by
  word. Real providers stream as they infer.
- English only, web chat only, inbound only.
