-- Demo seed data. Mirrors SEED_ORDERS in app/db/mock_store.py — keep the two in
-- step so a scenario behaves identically on either store.
--
-- Every table is schema-qualified deliberately. The target database also has a
-- `public.orders` belonging to an unrelated project; relying on `search_path`
-- alone would mean a missing `fte.orders` silently seeds a stranger's table.
--
-- Idempotent: safe to run repeatedly.

insert into fte.businesses (id, name, plan_tier) values
    ('biz_demo',  'Aeron Home Goods', 'core'),
    ('biz_other', 'Unrelated Seller', 'core')
on conflict (id) do nothing;

insert into fte.customers (business_id, email, name) values
    ('biz_demo',  'ayesha.k@example.com',       'Ayesha K.'),
    ('biz_demo',  'daniel.m@example.com',       'Daniel M.'),
    ('biz_demo',  'sofia.r@example.com',        'Sofia R.'),
    ('biz_other', 'someone@other.example.com',  'Other Tenant Customer')
on conflict (business_id, email) do nothing;

insert into fte.orders (business_id, order_id, customer_id, status, placed_at, carrier, tracking_number, eta, total)
select v.business_id, v.order_id, c.id, v.status, v.placed_at::date, v.carrier, v.tracking_number, v.eta::date, v.total::numeric
from (values
    ('biz_demo',  'ORD-1001', 'ayesha.k@example.com',      'delivered',  '2026-06-28', 'DHL Express', 'DHL7742119003', '2026-07-02', '149.00'),
    ('biz_demo',  'ORD-1002', 'ayesha.k@example.com',      'in_transit', '2026-07-19', 'FedEx',       'FX884120774',   '2026-07-29', '59.00'),
    ('biz_demo',  'ORD-1003', 'daniel.m@example.com',      'delivered',  '2026-04-11', 'DHL Express', 'DHL7740028851', '2026-04-16', '89.00'),
    ('biz_demo',  'ORD-1004', 'sofia.r@example.com',       'processing', '2026-07-24', null,          null,            '2026-08-01', '420.00'),
    -- Second tenant, deliberately reusing the id ORD-1002 so cross-tenant
    -- isolation can actually be tested rather than merely asserted.
    ('biz_other', 'ORD-1002', 'someone@other.example.com', 'cancelled',  '2026-07-01', null,          null,            null,         '10.00')
) as v (business_id, order_id, email, status, placed_at, carrier, tracking_number, eta, total)
join fte.customers c on c.business_id = v.business_id and c.email = v.email
on conflict (business_id, order_id) do nothing;

-- Line items. Quantities are what the tool reports as `item_count`.
insert into fte.order_items (business_id, order_ref, product_name, qty, unit_price)
select v.business_id, o.id, v.product_name, v.qty, v.unit_price::numeric
from (values
    ('biz_demo',  'ORD-1001', 'AeroDesk Standing Desk',   1, '149.00'),
    ('biz_demo',  'ORD-1002', 'AeroChair Lumbar Cushion', 2, '29.50'),
    ('biz_demo',  'ORD-1003', 'AeroChair Footrest',       1, '89.00'),
    ('biz_demo',  'ORD-1004', 'AeroDesk Cable Tray',      3, '140.00'),
    ('biz_other', 'ORD-1002', 'Unrelated Item',           1, '10.00')
) as v (business_id, order_id, product_name, qty, unit_price)
join fte.orders o on o.business_id = v.business_id and o.order_id = v.order_id
where not exists (
    select 1 from fte.order_items oi
    where oi.order_ref = o.id and oi.product_name = v.product_name
);
