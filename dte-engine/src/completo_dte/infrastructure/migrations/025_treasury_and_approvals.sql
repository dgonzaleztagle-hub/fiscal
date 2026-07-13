CREATE TABLE financial_obligations (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, direction TEXT NOT NULL CHECK(direction IN ('receivable','payable')),
 counterparty_ref TEXT NOT NULL, counterparty_name TEXT NOT NULL, source_ref TEXT NOT NULL,
 branch_id TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), due_on TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('open','partial','paid','cancelled')), created_at TEXT NOT NULL,
 UNIQUE(tenant_id,direction,source_ref)
);
CREATE TABLE obligation_payments (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, obligation_id TEXT NOT NULL REFERENCES financial_obligations(id),
 amount INTEGER NOT NULL CHECK(amount>0), paid_on TEXT NOT NULL, method TEXT NOT NULL,
 evidence_ref TEXT, actor_ref TEXT NOT NULL, idempotency_key TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(tenant_id,idempotency_key)
);
CREATE TABLE approval_requests (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, operation_type TEXT NOT NULL, operation_ref TEXT NOT NULL,
 amount INTEGER NOT NULL CHECK(amount>=0), requested_by TEXT NOT NULL, required_role TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','cancelled')),
 decided_by TEXT, reason TEXT, created_at TEXT NOT NULL, decided_at TEXT,
 UNIQUE(tenant_id,operation_type,operation_ref)
);
CREATE INDEX idx_obligations_due ON financial_obligations(tenant_id,direction,status,due_on);
CREATE INDEX idx_approvals_pending ON approval_requests(tenant_id,status,created_at);
