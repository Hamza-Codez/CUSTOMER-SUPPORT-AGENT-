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
