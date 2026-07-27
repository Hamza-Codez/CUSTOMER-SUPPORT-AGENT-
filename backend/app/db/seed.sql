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

insert into fte.policies (business_id, topic, body, source_ref) values
    ('biz_demo', 'Refund window',
     'Refunds are available within 30 days of delivery, provided the item is unused and in its original packaging. Refunds are issued to the original payment method and take 5-10 business days to appear.',
     'refund-policy.md#refund-window'),
    ('biz_demo', 'Damaged or faulty goods',
     'If an item arrives damaged or develops a fault within 30 days, we replace or refund it in full including original shipping. Photographs of the damage help us process the claim faster, but are not required.',
     'refund-policy.md#damaged-goods'),
    ('biz_demo', 'How to start a return',
     'To return an item, contact support with your order number. We email a prepaid return label. Returns are free for faulty goods; for change-of-mind returns a 4.99 label fee is deducted from the refund.',
     'returns-policy.md#starting-a-return'),
    ('biz_demo', 'Order processing and dispatch',
     'Orders placed before 2pm on a working day are dispatched the same day. Orders placed after 2pm, at weekends, or on public holidays are dispatched the next working day.',
     'shipping-policy.md#dispatch'),
    ('biz_demo', 'Delivery times and methods',
     'Standard delivery takes 3-5 working days and is free over 50. Express delivery takes 1-2 working days and costs 7.99. Large items such as desks are delivered by a two-person carrier team on a booked slot.',
     'shipping-policy.md#delivery-times'),
    ('biz_demo', 'Warranty cover',
     'Desks and chairs carry a 5 year warranty on frames and mechanisms. Accessories carry 1-2 years. Warranty covers manufacturing defects, not accidental damage or normal wear.',
     'warranty-policy.md#cover'),
    ('biz_other', 'Unrelated seller policy',
     'Belongs to another tenant and must never surface for biz_demo.',
     'other-tenant.md#fixture')
on conflict (business_id, source_ref) do nothing;

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
