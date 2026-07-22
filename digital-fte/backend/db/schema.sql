-- GENERATED FILE — do not edit.
-- Built from db/migrations/ by scripts/build_schema.py.
--
-- Paste the whole thing into the Supabase SQL Editor and run it once. It is
-- idempotent: every statement is CREATE IF NOT EXISTS / CREATE OR REPLACE /
-- ON CONFLICT, so re-running is safe.


-- ==========================================================
-- 0001_init.sql
-- ==========================================================
-- Digital FTE — Customer Support Agent · schema v1
-- Run once against a fresh Supabase project (SQL Editor, or `supabase db push`).
-- Mirrors SPEC §4 exactly: the shapes returned by store.* do not change.

create extension if not exists vector;

-- --- orders -----------------------------------------------------------------
create table if not exists orders (
  order_id   text primary key,                 -- ORD-####
  customer   text        not null,
  items      jsonb       not null,             -- list[str]
  total      numeric     not null,
  status     text        not null,             -- processing | shipped | delivered
  carrier    text,
  tracking   text,
  eta        date,
  refundable boolean     not null default false -- enforced in code by process_refund
);

-- --- tickets (the audit trail) ----------------------------------------------
-- IDs are generated server-side so concurrent workers can never collide.
create sequence if not exists ticket_seq;

create table if not exists tickets (
  id         text primary key
             default 'TCK-' || lpad(nextval('ticket_seq')::text, 4, '0'),
  subject    text        not null,
  detail     text,
  priority   text        not null default 'normal'
             check (priority in ('low', 'normal', 'high')),
  escalated  boolean     not null default false,
  order_id   text        references orders(order_id),
  status     text        not null default 'open',
  created_at timestamptz not null default now()
);

-- The dashboard reads newest-first; the tiebreak keeps ordering deterministic
-- when two tickets land inside the same clock tick.
create index if not exists tickets_created_at_idx on tickets (created_at desc, id desc);
create index if not exists tickets_escalated_idx  on tickets (escalated) where escalated;

-- --- knowledge base (RAG) ----------------------------------------------------
-- vector(1536) matches EMBEDDING_DIM. Changing the embedding model to one with
-- different dimensions requires altering this column AND rebuilding the index.
create table if not exists kb_docs (
  id        bigserial primary key,
  title     text not null unique,              -- unique so ingest can upsert
  body      text not null,
  embedding vector(1536)
);

create index if not exists kb_docs_embedding_idx
  on kb_docs using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- --- retrieval RPC -----------------------------------------------------------
-- store.search_kb calls this. Returns the same {title, body} shape the mock
-- backend returns, so nothing upstream changes.
create or replace function match_kb_docs(
  query_embedding vector(1536),
  match_count     int   default 3,
  min_similarity  float default 0.05
)
returns table (title text, body text, similarity float)
language sql stable
as $$
  select d.title,
         d.body,
         1 - (d.embedding <=> query_embedding) as similarity
  from kb_docs d
  where d.embedding is not null
    and 1 - (d.embedding <=> query_embedding) >= min_similarity
  order by d.embedding <=> query_embedding
  limit match_count;
$$;

-- ==========================================================
-- 0002_seed_orders.sql
-- ==========================================================
-- Seed the demo orders — the same three the mock store serves, so a demo
-- behaves identically on either backend. ETAs are relative to run date.
-- KB documents are seeded separately by scripts/ingest_kb.py (they need embeddings).

insert into orders (order_id, customer, items, total, status, carrier, tracking, eta, refundable)
values
  ('ORD-1001', 'Jordan Lee',
   '["AeroDesk Standing Desk (oak)"]'::jsonb,
   499.00, 'shipped', 'DHL', 'DHL-88231145', current_date + 2, true),

  ('ORD-1002', 'Priya Nair',
   '["AeroChair Ergonomic Chair"]'::jsonb,
   329.00, 'delivered', 'FedEx', 'FDX-55190022', current_date - 1, true),

  -- Not yet shipped: the out-of-policy case process_refund must refuse.
  ('ORD-1003', 'Sam Okoro',
   '["AeroDesk Standing Desk (walnut)", "AeroChair Ergonomic Chair"]'::jsonb,
   828.00, 'processing', null, null, current_date + 6, false)

on conflict (order_id) do update set
  customer   = excluded.customer,
  items      = excluded.items,
  total      = excluded.total,
  status     = excluded.status,
  carrier    = excluded.carrier,
  tracking   = excluded.tracking,
  eta        = excluded.eta,
  refundable = excluded.refundable;

-- ==========================================================
-- 0003_sessions.sql
-- ==========================================================
-- Conversation memory — the FTE's third trait, moved out of process memory.
-- One row per session, rewritten each turn. Messages are the LangChain
-- serialized form (messages_to_dict), stored verbatim as jsonb.

create table if not exists sessions (
  session_id text primary key,
  messages   jsonb       not null default '[]'::jsonb,
  updated_at timestamptz not null default now()
);

-- Sessions are not an audit trail; they are working memory and may be pruned.
-- Nothing prunes them automatically in v1 — a session row lives until it is
-- explicitly cleared. To age them out on a schedule, run something like:
--   delete from sessions where updated_at < now() - interval '30 days';
create index if not exists sessions_updated_at_idx on sessions (updated_at);

-- ==========================================================
-- 0004_user_scoping.sql
-- ==========================================================
-- Per-user scoping (Phase 4).
--
-- `user_id` holds the Supabase Auth user id (auth.users.id). A NULL means a
-- shared demo fixture, visible to everyone — that is how the three canonical
-- ORD-1001/1002/1003 rows keep working. An owned row is visible only to its
-- owner; the store enforces that, and RLS below is defence in depth.

alter table orders  add column if not exists user_id uuid references auth.users(id) on delete cascade;
alter table tickets add column if not exists user_id uuid references auth.users(id) on delete set null;

create index if not exists orders_user_id_idx  on orders (user_id);
create index if not exists tickets_user_id_idx on tickets (user_id);

-- Seeded order ids live well clear of the canonical 1001-1003 block, so
-- order_id stays the primary key and tickets.order_id keeps referencing it.
create sequence if not exists demo_order_seq start 2001;

-- Onboarding: one call gives a new signup their own three orders — one shipped,
-- one delivered and refundable, one processing and NOT refundable, so the demo
-- can show both an approval and a refusal. Idempotent per user.
create or replace function seed_demo_orders(p_user_id uuid)
returns setof orders
language plpgsql
as $$
declare
  seeded_count int;
begin
  select count(*) into seeded_count from orders where user_id = p_user_id;

  if seeded_count = 0 then
    insert into orders (order_id, customer, items, total, status, carrier, tracking, eta, refundable, user_id)
    values
      ('ORD-' || lpad(nextval('demo_order_seq')::text, 4, '0'), 'You',
       '["AeroDesk Standing Desk (oak)"]'::jsonb, 499.00, 'shipped',
       'DHL', 'DHL-88231145', current_date + 2, true, p_user_id),

      ('ORD-' || lpad(nextval('demo_order_seq')::text, 4, '0'), 'You',
       '["AeroChair Ergonomic Chair"]'::jsonb, 329.00, 'delivered',
       'FedEx', 'FDX-55190022', current_date - 1, true, p_user_id),

      ('ORD-' || lpad(nextval('demo_order_seq')::text, 4, '0'), 'You',
       '["AeroDesk Standing Desk (walnut)"]'::jsonb, 828.00, 'processing',
       null, null, current_date + 6, false, p_user_id);
  end if;

  return query select * from orders where user_id = p_user_id order by order_id;
end;
$$;

-- --- Row-level security ------------------------------------------------------
-- The backend connects with the service key, which bypasses RLS, so these
-- policies are not what protects the app today — FastAPI is. They exist so that
-- if anything ever connects with a user's own token (a direct browser query,
-- a future Realtime subscription), the database refuses on its own.

alter table orders  enable row level security;
alter table tickets enable row level security;

drop policy if exists orders_owner_read on orders;
create policy orders_owner_read on orders
  for select using (user_id is null or user_id = auth.uid());

-- Tickets are the audit log: a customer sees only their own, an agent sees all.
drop policy if exists tickets_owner_read on tickets;
create policy tickets_owner_read on tickets
  for select using (
    user_id = auth.uid()
    or coalesce(auth.jwt() -> 'app_metadata' ->> 'role', '') = 'agent'
  );

-- ==========================================================
-- 0005_fix_vector_index.sql
-- ==========================================================
-- Fix: vector search returned zero rows on a correctly-populated table.
--
-- 0001 created an ivfflat index with lists = 100 while kb_docs was still empty.
-- ivfflat is a *trained* index: it clusters existing rows into `lists` cells and
-- a query probes only `ivfflat.probes` of them (default 1). Built on an empty
-- table, the centroids are degenerate; with 5 rows and 100 lists, the one list a
-- query probes is almost certainly empty — so a perfectly good match is never
-- looked at and the KB appears to contain nothing.
--
-- HNSW is not trained. It builds incrementally as rows arrive, needs no minimum
-- row count, and gives exact-ish recall at this size. For a knowledge base of
-- hundreds-to-thousands of passages it is simply the right choice.

drop index if exists kb_docs_embedding_idx;

create index if not exists kb_docs_embedding_hnsw
  on kb_docs using hnsw (embedding vector_cosine_ops);

-- Recreated so similarity is computed once and NULL can never silently filter
-- every row: an uncastable query_embedding used to make the comparison NULL,
-- which is not true, which returned nothing — indistinguishable from "no match".
create or replace function match_kb_docs(
  query_embedding vector(1536),
  match_count     int   default 3,
  min_similarity  float default 0.05
)
returns table (title text, body text, similarity float)
language sql stable
as $$
  select d.title, d.body, s.similarity
  from kb_docs d
  cross join lateral (
    select 1 - (d.embedding <=> query_embedding) as similarity
  ) s
  where d.embedding is not null
    and query_embedding is not null
    and s.similarity >= min_similarity
  order by s.similarity desc
  limit match_count;
$$;
