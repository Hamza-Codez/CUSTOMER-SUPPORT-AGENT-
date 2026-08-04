-- Digital FTE — Phase 1 schema.
--
-- Everything lives in a dedicated `fte` schema rather than `public`. The target
-- database already hosts unrelated projects whose tables collide with ours by
-- name (`orders`, `products`, `users`), and `create table if not exists` would
-- silently bind to those instead — which is exactly how you end up with a
-- foreign key pointing at a stranger's table. Namespacing is additive: nothing
-- outside `fte` is touched.
--
-- Only the tables Phase 1 actually uses are created here. The full spec also
-- defines policies, refunds, escalations and subscriptions; those arrive with
-- the phases that use them rather than sitting empty in the meantime.
--
-- `business_id` is on every tenant-scoped table. It is the tenancy key the tool
-- layer filters on for every read and write.

create schema if not exists fte;

-- pgvector, for policy retrieval. Verified available on the target instance at
-- version 0.8.0.
create extension if not exists vector;

create table if not exists fte.businesses (
    id          text primary key,
    name        text        not null,
    plan_tier   text        not null default 'core',
    created_at  timestamptz not null default now()
);

create table if not exists fte.customers (
    id          bigserial primary key,
    business_id text        not null references fte.businesses (id) on delete cascade,
    email       text        not null,
    name        text        not null,
    created_at  timestamptz not null default now(),
    unique (business_id, email)
);

create table if not exists fte.orders (
    id              bigserial primary key,
    business_id     text        not null references fte.businesses (id) on delete cascade,
    -- Customer-facing identifier (ORD-1002). Unique per tenant, not globally:
    -- two businesses may legitimately both have an "ORD-1002".
    order_id        text        not null,
    customer_id     bigint      not null references fte.customers (id) on delete cascade,
    status          text        not null,
    placed_at       date        not null,
    carrier         text,
    tracking_number text,
    eta             date,
    total           numeric(12, 2) not null default 0,
    created_at      timestamptz not null default now(),
    unique (business_id, order_id)
);

create table if not exists fte.order_items (
    id           bigserial primary key,
    business_id  text   not null references fte.businesses (id) on delete cascade,
    order_ref    bigint not null references fte.orders (id) on delete cascade,
    product_name text   not null,
    qty          int    not null default 1,
    unit_price   numeric(12, 2) not null default 0
);

create index if not exists order_items_order_idx on fte.order_items (order_ref);

create table if not exists fte.products (
    product_id  text        not null,
    business_id text        not null references fte.businesses (id) on delete cascade,
    name        text        not null,
    price       numeric(12, 2) not null default 0,
    stock       int         not null default 0,
    summary     text        not null default '',
    -- Comparison points, flat key/value so the compare card stays category-agnostic.
    attributes  jsonb       not null default '{}'::jsonb,
    created_at  timestamptz not null default now(),
    primary key (business_id, product_id)
);

-- Parsed passages of the seller's written policy, produced by app/rag/parser.py
-- from the markdown in app/db/knowledge/. `source_ref` is not nullable on
-- purpose: a passage that cannot be cited is one the agent must not use, and the
-- grounding guardrail depends on that being true at the source.
--
-- The embedding dimension is fixed by EMBEDDING_DIM (1536). Changing that config
-- means altering this column and re-running scripts/ingest_kb.py — the vectors
-- from one model are meaningless to another.
--
-- Deliberately no ivfflat/hnsw index. This corpus is a handful of rows, where a
-- sequential scan is both exact and faster than an approximate index, and an
-- ivfflat index built before the rows exist silently returns nothing — a trap
-- worth simply not walking into. Add one when the corpus justifies it, after the
-- data is loaded.
create table if not exists fte.policies (
    id          bigserial primary key,
    business_id text        not null references fte.businesses (id) on delete cascade,
    doc         text        not null default '',
    topic       text        not null,
    body        text        not null,
    source_ref  text        not null,
    embedding   vector(1536),
    created_at  timestamptz not null default now(),
    unique (business_id, source_ref)
);

-- Money. The unique constraint on (business_id, order_id) is the last line of
-- defence against paying the same order twice: a retried run, a duplicated
-- request or a second operator approval all collide here rather than in memory.
create table if not exists fte.refunds (
    id          bigserial primary key,
    refund_id   text        not null unique,
    business_id text        not null references fte.businesses (id) on delete cascade,
    order_id    text        not null,
    amount      numeric(12, 2) not null,
    reason      text        not null default '',
    status      text        not null,
    approved_by text,
    created_at  timestamptz not null default now(),
    unique (business_id, order_id)
);

-- The operator queue. `run_state` is a serialised Agents SDK RunState: it is what
-- lets a run pause for approval now and resume in a different process later,
-- continuing from exactly where it stopped instead of being re-improvised.
create table if not exists fte.escalations (
    id                bigserial primary key,
    escalation_id     text        not null unique,
    business_id       text        not null references fte.businesses (id) on delete cascade,
    session_id        text        not null,
    status            text        not null default 'pending',
    decision_card     jsonb       not null,
    run_state         jsonb,
    resolved_by       text,
    resolution_reason text,
    created_at        timestamptz not null default now()
);

create index if not exists escalations_queue_idx
    on fte.escalations (business_id, status, created_at desc);

-- Agent conversation memory. Backs our SessionABC implementation: `item` is the
-- raw Agents SDK input item, `role` is denormalised purely so the transcript is
-- readable in SQL. Ordering is by `id`.
create table if not exists fte.messages (
    id          bigserial primary key,
    business_id text        not null,
    session_id  text        not null,
    role        text,
    item        jsonb       not null,
    created_at  timestamptz not null default now()
);

create index if not exists messages_session_idx
    on fte.messages (business_id, session_id, id);

-- Every sensitive read and write lands here. This is the backbone of trust for a
-- system that will later move money.
create table if not exists fte.audit_logs (
    id          bigserial primary key,
    business_id text        not null,
    actor       text        not null,
    action      text        not null,
    target      text        not null,
    outcome     text        not null,
    detail      jsonb       not null default '{}'::jsonb,
    ts          timestamptz not null default now()
);

create index if not exists audit_logs_biz_ts_idx on fte.audit_logs (business_id, ts desc);

-- Identities proven during a conversation. Verification has to outlive a single
-- turn: a customer who proved who they are and then asks a follow-up is still
-- the same person, and re-asking every message defeats the point (SPEC §5.3).
-- Keyed the same way the conversation is, so nothing carries across tenants or
-- across conversations.
create table if not exists fte.session_verifications (
    id          bigserial primary key,
    business_id text        not null references fte.businesses (id) on delete cascade,
    session_id  text        not null,
    order_id    text        not null,
    email       text        not null,
    name        text        not null default '',
    verified_at timestamptz not null default now(),
    unique (business_id, session_id, order_id)
);

create index if not exists session_verifications_idx
    on fte.session_verifications (business_id, session_id);

-- Summary emails. The unique constraint on (business_id, session_id) is the
-- idempotency key: one summary per conversation, enforced by the database rather
-- than by the agent remembering whether it already sent one.
--
-- `feedback_token` is the capability in the emailed link. It is unguessable and
-- scoped to a single conversation, which is what lets the feedback endpoint be
-- unauthenticated — a recipient clicking a star in their mail client has no
-- session and cannot be asked to log in.
create table if not exists fte.emails (
    id             bigserial primary key,
    email_id       text        not null unique,
    business_id    text        not null references fte.businesses (id) on delete cascade,
    session_id     text        not null,
    recipient      text        not null,
    subject        text        not null,
    body_html      text        not null,
    feedback_token text        not null unique,
    status         text        not null,
    provider       text        not null,
    error          text,
    created_at     timestamptz not null default now(),
    unique (business_id, session_id)
);

-- CSAT. One response per token, so a double-click or a mail client prefetching
-- the link cannot inflate the numbers.
create table if not exists fte.feedback (
    id             bigserial primary key,
    business_id    text        not null references fte.businesses (id) on delete cascade,
    feedback_token text        not null unique references fte.emails (feedback_token) on delete cascade,
    session_id     text        not null,
    rating         int         not null check (rating between 1 and 5),
    comment        text,
    created_at     timestamptz not null default now()
);

create index if not exists feedback_biz_idx on fte.feedback (business_id, created_at desc);

-- Sellers asking to embed the FTE on their own site (SPEC §16.1). Deliberately
-- not a dead-end mailto: the request is a record an operator can work through.
create table if not exists fte.integration_requests (
    id            bigserial primary key,
    request_id    text        not null unique,
    business_id   text        not null references fte.businesses (id) on delete cascade,
    contact_name  text        not null,
    contact_email text        not null,
    website       text        not null default '',
    platform      text        not null default '',
    monthly_conversations text not null default '',
    notes         text        not null default '',
    status        text        not null default 'new',
    created_at    timestamptz not null default now()
);

create index if not exists integration_requests_biz_idx
    on fte.integration_requests (business_id, created_at desc);

-- Token accounting, per conversation turn. Without this "cost per conversation"
-- (SPEC §16.5, §19) is a number nobody can produce, and a made-up one is worse
-- than none. `provider` is stored because usage from the mock provider is always
-- zero and must never be presented as a real cost.
create table if not exists fte.conversation_usage (
    id            bigserial primary key,
    business_id   text        not null references fte.businesses (id) on delete cascade,
    session_id    text        not null,
    provider      text        not null,
    model         text        not null default '',
    requests      int         not null default 0,
    input_tokens  int         not null default 0,
    output_tokens int         not null default 0,
    ts            timestamptz not null default now()
);

create index if not exists conversation_usage_biz_idx
    on fte.conversation_usage (business_id, ts desc);

-- Seller accounts. Sign-up is for sellers, not shoppers: an end customer is
-- identified by order id + email because the widget lives on the seller's own
-- site, so they have no account here to have.
--
-- `email` is unique platform-wide rather than per business, because login
-- happens before we know which business someone belongs to.
create table if not exists fte.users (
    id            bigserial primary key,
    user_id       text        not null unique,
    username      text        not null unique,
    business_id   text        not null references fte.businesses (id) on delete cascade,
    email         text        not null unique,
    name          text        not null,
    password_hash text        not null,
    role          text        not null default 'operator',
    created_at    timestamptz not null default now()
);

create index if not exists users_business_idx on fte.users (business_id);

-- Public credentials that ship inside a storefront's HTML. Weakest thing we
-- issue: it can start a customer conversation and nothing else.
--
-- `key` is the primary lookup and is not tenant-scoped in the query — the key is
-- what establishes the tenant, so it cannot be scoped by it. `allowed_origins`
-- is what makes lifting the key out of someone's page source useless: a
-- production key with no origins recorded is refused everywhere.
--
-- Revoked keys are kept. A key that appears in an audit entry has to stay
-- resolvable or the entry stops explaining itself.
create table if not exists fte.site_keys (
    id              bigserial primary key,
    key             text        not null unique,
    business_id     text        not null references fte.businesses (id) on delete cascade,
    label           text        not null default '',
    allowed_origins text[]      not null default '{}',
    preview         boolean     not null default false,
    created_at      timestamptz not null default now(),
    revoked_at      timestamptz
);

create index if not exists site_keys_business_idx
    on fte.site_keys (business_id, created_at desc);

-- --------------------------------------------------------------------------
-- Additive migrations
--
-- `create table if not exists` does nothing to a table that already exists, so
-- columns added after a database was first created never appear. Anything added
-- to a table above must also be stated here to reach an existing deployment.
-- Both forms are idempotent, so this file stays safe to re-run.
-- --------------------------------------------------------------------------

alter table fte.policies add column if not exists doc text not null default '';
alter table fte.policies add column if not exists embedding vector(1536);
alter table fte.users add column if not exists username text not null default '';

-- --------------------------------------------------------------------------
-- New Onboarding & Platform Tables
-- --------------------------------------------------------------------------

create table if not exists fte.profiles (
    user_id       text        not null primary key references fte.users (user_id) on delete cascade,
    whatsapp      text        not null default '',
    store_name    text        not null default '',
    store_url     text        not null default '',
    policies_text text        not null default '',
    brand_voice   text        not null default '',
    status        text        not null default 'pending',
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create table if not exists fte.subscriptions (
    user_id       text        not null primary key references fte.users (user_id) on delete cascade,
    plan          text        not null default 'trial',
    trial_ends    timestamptz not null,
    created_at    timestamptz not null default now()
);

create table if not exists fte.integrations (
    user_id       text        not null primary key references fte.users (user_id) on delete cascade,
    flavour       text        not null default 'A',
    kb_id         text,
    widget_key    text,
    scraped_at    timestamptz,
    created_at    timestamptz not null default now()
);
