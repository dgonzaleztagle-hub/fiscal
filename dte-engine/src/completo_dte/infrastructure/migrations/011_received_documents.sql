CREATE TABLE received_fiscal_documents (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    receiver_rut TEXT NOT NULL,
    issuer_rut TEXT NOT NULL,
    issuer_name TEXT NOT NULL,
    document_type INTEGER NOT NULL CHECK (document_type IN (33, 34, 52, 56, 61)),
    folio INTEGER NOT NULL CHECK (folio > 0),
    issued_on TEXT NOT NULL,
    total INTEGER NOT NULL CHECK (total >= 0),
    document_id TEXT NOT NULL,
    xml_sha256 TEXT NOT NULL CHECK (length(xml_sha256) = 64),
    signed_xml BLOB NOT NULL CHECK (length(signed_xml) > 0),
    source TEXT NOT NULL CHECK (source IN ('upload', 'email', 'official_connector')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'claimed_partial', 'claimed_total')),
    sii_received_at TEXT,
    received_at TEXT NOT NULL,
    UNIQUE (tenant_id, issuer_rut, document_type, folio),
    UNIQUE (tenant_id, xml_sha256)
);

CREATE INDEX idx_received_documents_inbox
ON received_fiscal_documents (tenant_id, status, issued_on DESC);

CREATE TRIGGER received_documents_immutable
BEFORE UPDATE OF tenant_id, receiver_rut, issuer_rut, issuer_name, document_type,
                 folio, issued_on, total, document_id, xml_sha256, signed_xml,
                 source, sii_received_at, received_at
ON received_fiscal_documents
BEGIN
  SELECT RAISE(ABORT, 'received fiscal payload is immutable');
END;

CREATE TRIGGER received_documents_no_delete
BEFORE DELETE ON received_fiscal_documents
BEGIN
  SELECT RAISE(ABORT, 'received fiscal documents cannot be deleted');
END;
