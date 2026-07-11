CREATE TABLE received_document_classifications (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    received_document_id TEXT NOT NULL REFERENCES received_fiscal_documents(id),
    version INTEGER NOT NULL CHECK (version > 0),
    provider_id TEXT,
    destination TEXT NOT NULL CHECK (destination IN ('expense', 'inventory', 'fixed_asset', 'mixed', 'unassigned')),
    category_code TEXT,
    notes TEXT,
    classified_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (received_document_id, version)
);

CREATE INDEX idx_received_classifications_latest
ON received_document_classifications (tenant_id, received_document_id, version DESC);

CREATE TRIGGER received_classifications_no_update
BEFORE UPDATE ON received_document_classifications
BEGIN
  SELECT RAISE(ABORT, 'received classifications are append-only');
END;

CREATE TRIGGER received_classifications_no_delete
BEFORE DELETE ON received_document_classifications
BEGIN
  SELECT RAISE(ABORT, 'received classifications cannot be deleted');
END;
