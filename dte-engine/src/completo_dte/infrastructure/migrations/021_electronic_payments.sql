CREATE TABLE electronic_payments (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    terminal_id TEXT NOT NULL,
    authorization_code TEXT NOT NULL,
    provider_reference TEXT NOT NULL,
    sale_ref TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0),
    occurred_at TEXT NOT NULL,
    settlement_ref TEXT,
    source TEXT NOT NULL CHECK (source IN ('pos_integration', 'provider_import', 'manual')),
    imported_at TEXT NOT NULL,
    UNIQUE (tenant_id, provider, terminal_id, authorization_code, provider_reference)
);

CREATE TABLE payment_reconciliation_snapshots (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    period TEXT NOT NULL CHECK (length(period) = 7),
    version INTEGER NOT NULL CHECK (version > 0),
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (tenant_id, period, version),
    UNIQUE (tenant_id, period, payload_sha256)
);

CREATE TRIGGER electronic_payments_no_update BEFORE UPDATE ON electronic_payments
BEGIN SELECT RAISE(ABORT, 'electronic payments are immutable'); END;
CREATE TRIGGER electronic_payments_no_delete BEFORE DELETE ON electronic_payments
BEGIN SELECT RAISE(ABORT, 'electronic payments cannot be deleted'); END;
CREATE TRIGGER payment_reconciliation_no_update BEFORE UPDATE ON payment_reconciliation_snapshots
BEGIN SELECT RAISE(ABORT, 'payment reconciliation snapshots are immutable'); END;
CREATE TRIGGER payment_reconciliation_no_delete BEFORE DELETE ON payment_reconciliation_snapshots
BEGIN SELECT RAISE(ABORT, 'payment reconciliation snapshots cannot be deleted'); END;
