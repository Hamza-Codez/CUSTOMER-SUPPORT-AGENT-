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
