CREATE TABLE fiscal_deliveries (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_record_id TEXT NOT NULL REFERENCES fiscal_documents(id),
    recipient_email TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('invoice_exchange')),
    exchange_xml_sha256 TEXT NOT NULL CHECK (length(exchange_xml_sha256) = 64),
    exchange_xml BLOB NOT NULL CHECK (length(exchange_xml) > 0),
    pdf_sha256 TEXT NOT NULL CHECK (length(pdf_sha256) = 64),
    pdf BLOB NOT NULL CHECK (length(pdf) > 0),
    status TEXT NOT NULL CHECK (status IN ('queued', 'sending', 'sent', 'failed', 'unknown')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    provider_id TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (document_record_id, recipient_email, kind)
);

CREATE INDEX idx_fiscal_deliveries_pending
ON fiscal_deliveries (tenant_id, status, updated_at);

CREATE TRIGGER fiscal_deliveries_immutable_payload
BEFORE UPDATE OF tenant_id, document_record_id, recipient_email, kind,
                 exchange_xml_sha256, exchange_xml, pdf_sha256, pdf, created_at
ON fiscal_deliveries
BEGIN
  SELECT RAISE(ABORT, 'fiscal delivery payload is immutable');
END;

CREATE TRIGGER fiscal_deliveries_no_delete
BEFORE DELETE ON fiscal_deliveries
BEGIN
  SELECT RAISE(ABORT, 'fiscal deliveries cannot be deleted');
END;
