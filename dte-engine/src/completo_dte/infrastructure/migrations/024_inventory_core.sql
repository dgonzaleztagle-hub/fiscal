CREATE TABLE inventory_products (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, sku TEXT NOT NULL,
  name TEXT NOT NULL, unit TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, UNIQUE (tenant_id, sku)
);
CREATE TABLE inventory_movements (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  product_id TEXT NOT NULL REFERENCES inventory_products(id),
  branch_id TEXT NOT NULL, movement_type TEXT NOT NULL CHECK
    (movement_type IN ('purchase','sale','transfer_in','transfer_out','adjustment_in','adjustment_out','return_in','return_out')),
  quantity TEXT NOT NULL, source_ref TEXT NOT NULL, reason TEXT NOT NULL,
  actor_ref TEXT NOT NULL, idempotency_key TEXT NOT NULL, occurred_at TEXT NOT NULL,
  UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX idx_inventory_balance ON inventory_movements (tenant_id, branch_id, product_id, occurred_at);
