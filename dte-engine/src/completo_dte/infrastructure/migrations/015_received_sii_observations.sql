CREATE TABLE received_sii_observations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    received_document_id TEXT NOT NULL REFERENCES received_fiscal_documents(id),
    sii_received_at TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    UNIQUE (received_document_id, sii_received_at)
);

CREATE INDEX idx_received_sii_observations_latest
ON received_sii_observations (tenant_id, received_document_id, observed_at DESC);

CREATE TRIGGER received_sii_observations_no_update BEFORE UPDATE ON received_sii_observations
BEGIN SELECT RAISE(ABORT, 'sii observations are immutable'); END;
CREATE TRIGGER received_sii_observations_no_delete BEFORE DELETE ON received_sii_observations
BEGIN SELECT RAISE(ABORT, 'sii observations cannot be deleted'); END;
