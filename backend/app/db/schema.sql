-- Digital FTE — Phase 1 schema.
--
-- Only the tables Phase 1 actually uses are created here. The full spec also
-- defines products, policies, refunds, escalations and subscriptions; those
-- arrive with the phases that use them rather than sitting empty in the meantime.
--
-- `business_id` is on every tenant-scoped table. It is the tenancy key the tool
-- layer filters on for every read and write.

create table if not exists businesses (
    id          text primary key,
    name        text        not null,
    plan_tier   text        not null default 'core',
    created_at  timestamptz not null default now()
);

create table if not exists customers (
    id          bigserial primary key,
    business_id text        not null references businesses (id) on delete cascade,
    email       text        not null,
    name        text        not null,
    created_at  timestamptz not null default now(),
    unique (business_id, email)
);

create table if not exists orders (
    id              bigserial primary key,
    business_id     text        not null references businesses (id) on delete cascade,
    -- Customer-facing identifier (ORD-1002). Unique per tenant, not globally:
    -- two businesses may legitimately both have an "ORD-1002".
    order_id        text        not null,
    customer_id     bigint      not null references customers (id) on delete cascade,
    status          text        not null,
    placed_at       date        not null,
    carrier         text,
    tracking_number text,
    eta             date,
    total           numeric(12, 2) not null default 0,
    created_at      timestamptz not null default now(),
    unique (business_id, order_id)
);

create table if not exists order_items (
    id           bigserial primary key,
    business_id  text   not null references businesses (id) on delete cascade,
    order_ref    bigint not null references orders (id) on delete cascade,
    product_name text   not null,
    qty          int    not null default 1,
    unit_price   numeric(12, 2) not null default 0
);

create index if not exists order_items_order_idx on order_items (order_ref);

-- Agent conversation memory. Backs our SessionABC implementation: `item` is the
-- raw Agents SDK input item, `role` is denormalised purely so the transcript is
-- readable in SQL. Ordering is by `id`.
create table if not exists messages (
    id          bigserial primary key,
    business_id text        not null,
    session_id  text        not null,
    role        text,
    item        jsonb       not null,
    created_at  timestamptz not null default now()
);

create index if not exists messages_session_idx
    on messages (business_id, session_id, id);

-- Every sensitive read and write lands here. This is the backbone of trust for a
-- system that will later move money.
create table if not exists audit_logs (
    id          bigserial primary key,
    business_id text        not null,
    actor       text        not null,
    action      text        not null,
    target      text        not null,
    outcome     text        not null,
    detail      jsonb       not null default '{}'::jsonb,
    ts          timestamptz not null default now()
);

create index if not exists audit_logs_biz_ts_idx on audit_logs (business_id, ts desc);
