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
