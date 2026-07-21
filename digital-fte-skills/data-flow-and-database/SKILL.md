---
name: data-flow-and-database
description: Design data flow and the database for the Digital FTE using Supabase (Postgres) and pgvector, swapping the mock store behind stable interfaces. Use when the user asks to design the schema, add a table, wire Supabase, set up the knowledge base or RAG/vector search, define how data moves between layers, add migrations, or replace the in-memory mock with a real database. Covers table design, the store interface, RAG retrieval, and safe mock-to-real swaps.
---

# Data Flow & Database

Data has exactly one owner and moves only through the `store.*` interface. The
mock store and the real Supabase store share identical function signatures, so
going to production is a swap, not a rewrite.

## Principles
1. **Interface over implementation.** The agent/tools call `store.get_order(id)`; they never know if it's a dict or Postgres.
2. **One owner per data type.** Orders, tickets, KB, and memory each have a single source of truth in the data layer.
3. **Swap, don't rewrite.** Real DB must satisfy the same signatures the mock already proved.
4. **Read paths are grounded.** KB search returns only stored content; no fabrication.

## The store interface (freeze these)
```python
get_order(order_id: str) -> dict | None
add_ticket(subject, detail, priority="normal", escalated=False, order_id=None) -> dict
list_tickets() -> list[dict]
search_kb(query: str) -> list[dict]      # keyword now -> vector later
```
Both mock and Supabase implementations must match these exactly.

## Instructions

### Step 1: Model the tables (Supabase / Postgres)
```sql
create table orders (
  order_id text primary key,
  customer text not null,
  items jsonb not null,
  total numeric not null,
  status text not null,           -- processing | shipped | delivered
  carrier text, tracking text, eta date,
  refundable boolean not null default false
);

create table tickets (
  id text primary key,            -- TCK-####
  subject text not null,
  detail text,
  priority text not null default 'normal',   -- low | normal | high
  escalated boolean not null default false,
  order_id text references orders(order_id),
  status text not null default 'open',
  created_at timestamptz not null default now()
);

-- knowledge base with vector search
create extension if not exists vector;
create table kb_docs (
  id bigserial primary key,
  title text not null,
  body text not null,
  embedding vector(1536)          -- match your embedding model dims
);
create index on kb_docs using ivfflat (embedding vector_cosine_ops);
```

### Step 2: Implement the store against the same signatures
Swap dict lookups for Supabase queries; keep the function names and return
shapes identical to the mock. Nothing upstream changes.

### Step 3: RAG retrieval for the knowledge base
1. On ingest: embed `title + body`, store in `kb_docs.embedding`.
2. On query: embed the query, run cosine similarity, return top-k rows.
3. `search_kb` returns the same shape as the mock (list of `{title, body}`), so the agent is unaffected.
Keep a keyword fallback for empty/edge queries.

### Step 4: Conversation memory
Move `SESSIONS` from an in-memory dict to a `sessions` table (or Redis) keyed by
`session_id`, storing serialized messages. Same get/set contract as the dict.

### Step 5: Data flow direction
```
UI -> API -> agent -> tool -> store -> DB
DB -> store -> tool result -> agent reply -> API -> UI
```
Data only crosses layers through these calls. No layer reaches two layers down.

### Step 6: Migrations & seeding
- Keep schema in versioned SQL migrations (Supabase migrations or plain `.sql`).
- Seed a small realistic dataset (a few orders, KB docs) for demos and tests.
- Never edit prod data by hand; change it through a migration or the app.

### Step 7: Verify the swap
- Run the existing tool tests against the Supabase store unchanged. If signatures match, they pass.
- Confirm `search_kb` returns relevant docs for known queries.
- Confirm tickets persist across restarts (they no longer vanish like the mock).

## Example
Move tickets to Supabase:
1. Create `tickets` table (above).
2. Rewrite `add_ticket`/`list_tickets` to insert/select — same signatures.
3. Run the agent guardrail tests unchanged; a processed refund now persists in the DB.

## Troubleshooting
- **Upstream code broke after DB swap:** a signature or return shape changed. Match the mock exactly.
- **Vector search returns nothing:** embedding dims mismatch or index missing. Align `vector(n)` with the model and create the ivfflat index.
- **Duplicate/failed inserts:** primary key collision. Generate ids server-side; upsert where appropriate.
- **Tickets vanish on restart:** still using the in-memory list. Point `store` at Supabase.
- **Slow KB queries:** missing/underbuilt index. Add/tune the ivfflat index and set `lists` appropriately.
