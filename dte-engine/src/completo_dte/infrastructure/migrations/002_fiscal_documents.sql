CREATE TABLE IF NOT EXISTS fiscal_documents (
    id TEXT PRIMARY KEY,
    lease_id TEXT NOT NULL UNIQUE REFERENCES folio_leases(id),
    tenant_id TEXT NOT NULL,
    taxpayer_rut TEXT NOT NULL,
    document_type INTEGER NOT NULL,
    folio INTEGER NOT NULL,
    document_id TEXT NOT NULL,
    xml_sha256 TEXT NOT NULL,
    signed_xml BLOB NOT NULL,
    created_at TEXT NOT NULL,
    CHECK (length(signed_xml) > 0),
    CHECK (length(xml_sha256) = 64),
    UNIQUE (taxpayer_rut, document_type, folio),
    UNIQUE (taxpayer_rut, document_id)
);

CREATE INDEX IF NOT EXISTS idx_fiscal_documents_tenant_created
ON fiscal_documents (tenant_id, created_at);
