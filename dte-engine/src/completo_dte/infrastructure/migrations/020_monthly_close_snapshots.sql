CREATE TABLE monthly_close_snapshots (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    period TEXT NOT NULL CHECK (length(period) = 7),
    version INTEGER NOT NULL CHECK (version > 0),
    formula_version TEXT NOT NULL,
    source_sha256 TEXT NOT NULL CHECK (length(source_sha256) = 64),
    calculation_sha256 TEXT NOT NULL CHECK (length(calculation_sha256) = 64),
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (tenant_id, period, version),
    UNIQUE (tenant_id, period, calculation_sha256)
);

CREATE TABLE monthly_close_reviews (
    id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES monthly_close_snapshots(id),
    tenant_id TEXT NOT NULL,
    actor_ref TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('opened', 'marked_ready', 'reviewed', 'frozen')),
    reason TEXT,
    occurred_at TEXT NOT NULL
);

CREATE INDEX monthly_close_period_idx
ON monthly_close_snapshots (tenant_id, period, version DESC);

CREATE TRIGGER monthly_close_snapshots_no_update
BEFORE UPDATE ON monthly_close_snapshots
BEGIN SELECT RAISE(ABORT, 'monthly close snapshots are immutable'); END;
CREATE TRIGGER monthly_close_snapshots_no_delete
BEFORE DELETE ON monthly_close_snapshots
BEGIN SELECT RAISE(ABORT, 'monthly close snapshots cannot be deleted'); END;
CREATE TRIGGER monthly_close_reviews_no_update
BEFORE UPDATE ON monthly_close_reviews
BEGIN SELECT RAISE(ABORT, 'monthly close reviews are immutable'); END;
CREATE TRIGGER monthly_close_reviews_no_delete
BEFORE DELETE ON monthly_close_reviews
BEGIN SELECT RAISE(ABORT, 'monthly close reviews cannot be deleted'); END;
