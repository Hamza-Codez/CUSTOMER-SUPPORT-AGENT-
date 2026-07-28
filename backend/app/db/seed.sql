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
    -- Small, recent and in policy: the only order refundable without a human.
    -- Its dates are reset relative to current_date below.
    ('biz_demo',  'ORD-1005', 'ayesha.k@example.com',      'delivered',  '2026-07-17', 'Royal Mail',  'RM4471200GB',   '2026-07-22', '19.99'),
    -- Second tenant, deliberately reusing the id ORD-1002 so cross-tenant
    -- isolation can actually be tested rather than merely asserted.
    ('biz_other', 'ORD-1002', 'someone@other.example.com', 'cancelled',  '2026-07-01', null,          null,            null,         '10.00')
) as v (business_id, order_id, email, status, placed_at, carrier, tracking_number, eta, total)
join fte.customers c on c.business_id = v.business_id and c.email = v.email
on conflict (business_id, order_id) do nothing;

-- Keep ORD-1005 inside the refund window permanently, and matching the relative
-- dates app/db/mock_store.py computes. Runs unconditionally, unlike the insert
-- above, because a row seeded weeks ago would otherwise age out of the window and
-- silently take the auto-refund demo with it.
update fte.orders
   set placed_at = current_date - 10,
       eta       = current_date - 5
 where business_id = 'biz_demo' and order_id = 'ORD-1005';

-- Catalogue. PRD-TRAY-1 is deliberately out of stock; PRD-OTHER-1 belongs to the
-- second tenant and must never surface for biz_demo.
insert into fte.products (business_id, product_id, name, price, stock, summary, attributes) values
    ('biz_demo', 'PRD-DESK-1',  'AeroDesk Pro Standing Desk',      149.00, 12,
     'Electric sit-stand desk with a memory controller and a solid bamboo top.',
     '{"height_range":"71-121 cm","top_material":"Bamboo","weight_capacity":"80 kg","adjustment":"Electric, 4 memory presets","warranty":"5 years","assembly":"About 25 minutes"}'::jsonb),
    ('biz_demo', 'PRD-DESK-2',  'AeroDesk Lite Standing Desk',      99.00, 30,
     'Manual crank sit-stand desk in a compact footprint for smaller rooms.',
     '{"height_range":"73-118 cm","top_material":"Laminate","weight_capacity":"60 kg","adjustment":"Manual crank","warranty":"2 years","assembly":"About 40 minutes"}'::jsonb),
    ('biz_demo', 'PRD-CHAIR-1', 'AeroChair Ergonomic Task Chair',  249.00,  5,
     'Mesh-back task chair with adjustable lumbar support and a headrest.',
     '{"back":"Breathable mesh","lumbar":"Adjustable, 4-way","armrests":"3D adjustable","weight_capacity":"120 kg","warranty":"5 years"}'::jsonb),
    ('biz_demo', 'PRD-CUSH-1',  'AeroChair Lumbar Cushion',         29.50, 80,
     'Memory-foam lumbar cushion that straps to most existing office chairs.',
     '{"fill":"Memory foam","cover":"Washable mesh","fitting":"Two-strap, fits most chairs","warranty":"1 year"}'::jsonb),
    ('biz_demo', 'PRD-TRAY-1',  'AeroDesk Cable Tray',             140.00,  0,
     'Under-desk cable management tray. Currently out of stock.',
     '{"length":"80 cm","mounting":"Clamp-on, no drilling","warranty":"2 years"}'::jsonb),
    ('biz_other','PRD-OTHER-1', 'Unrelated Seller Widget',          10.00,  3,
     'Belongs to another tenant and must never surface for biz_demo.',
     '{"note":"tenancy fixture"}'::jsonb)
on conflict (business_id, product_id) do nothing;

-- biz_demo's policies are NOT seeded here. They are parsed and embedded from the
-- markdown in app/db/knowledge/ by scripts/ingest_kb.py, so the documents are the
-- only source of policy text. A copy in this file would drift the first time
-- someone edited a policy and updated only one of the two.
--
-- Only the cross-tenant fixture lives here, because it is a test artefact rather
-- than a document the seller wrote. It has no embedding, so vector search never
-- returns it — which is the point: it must never surface for biz_demo.
-- `do update`, not `do nothing`: a row seeded before the `doc` column existed
-- would otherwise keep an empty value forever, and only show up as a parity
-- failure against the in-memory store much later.
insert into fte.policies (business_id, doc, topic, body, source_ref) values
    ('biz_other', 'other-tenant.md', 'Unrelated seller policy',
     'Belongs to another tenant and must never surface for biz_demo.',
     'other-tenant.md#fixture')
on conflict (business_id, source_ref) do update
    set doc = excluded.doc,
        topic = excluded.topic,
        body = excluded.body;

-- Line items. Quantities are what the tool reports as `item_count`.
insert into fte.order_items (business_id, order_ref, product_name, qty, unit_price)
select v.business_id, o.id, v.product_name, v.qty, v.unit_price::numeric
from (values
    ('biz_demo',  'ORD-1001', 'AeroDesk Standing Desk',   1, '149.00'),
    ('biz_demo',  'ORD-1002', 'AeroChair Lumbar Cushion', 2, '29.50'),
    ('biz_demo',  'ORD-1003', 'AeroChair Footrest',       1, '89.00'),
    ('biz_demo',  'ORD-1004', 'AeroDesk Cable Tray',      3, '140.00'),
    ('biz_demo',  'ORD-1005', 'AeroChair Felt Desk Mat',  1, '19.99'),
    ('biz_other', 'ORD-1002', 'Unrelated Item',           1, '10.00')
) as v (business_id, order_id, product_name, qty, unit_price)
join fte.orders o on o.business_id = v.business_id and o.order_id = v.order_id
where not exists (
    select 1 from fte.order_items oi
    where oi.order_ref = o.id and oi.product_name = v.product_name
);
