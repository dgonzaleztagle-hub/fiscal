CREATE TABLE people_monthly_summaries (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    period TEXT NOT NULL CHECK (length(period)=7),
    version INTEGER NOT NULL CHECK (version>0),
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256)=64),
    payload_json TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    UNIQUE (tenant_id,period,version),
    UNIQUE (tenant_id,period,payload_sha256)
);
CREATE TRIGGER people_summaries_no_update BEFORE UPDATE ON people_monthly_summaries
BEGIN SELECT RAISE(ABORT, 'people summaries are immutable'); END;
CREATE TRIGGER people_summaries_no_delete BEFORE DELETE ON people_monthly_summaries
BEGIN SELECT RAISE(ABORT, 'people summaries cannot be deleted'); END;
