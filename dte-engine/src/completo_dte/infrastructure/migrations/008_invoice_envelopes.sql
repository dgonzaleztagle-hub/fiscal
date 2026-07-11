PRAGMA foreign_keys = OFF;

CREATE TABLE fiscal_envelopes_new (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    taxpayer_rut TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('envio_boleta', 'envio_dte', 'rcof')),
    document_id TEXT NOT NULL,
    xml_sha256 TEXT NOT NULL,
    signed_xml BLOB NOT NULL,
    status TEXT NOT NULL DEFAULT 'prepared'
        CHECK (status IN ('prepared', 'submitting', 'submitted', 'accepted', 'accepted_with_objections', 'rejected', 'unknown')),
    track_id TEXT,
    remote_code TEXT,
    remote_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (length(signed_xml) > 0),
    CHECK (length(xml_sha256) = 64),
    UNIQUE (tenant_id, taxpayer_rut, kind, document_id)
);

INSERT INTO fiscal_envelopes_new
SELECT * FROM fiscal_envelopes;

DROP TABLE fiscal_envelopes;
ALTER TABLE fiscal_envelopes_new RENAME TO fiscal_envelopes;

CREATE INDEX idx_fiscal_envelopes_pending
ON fiscal_envelopes (status, updated_at);

CREATE TRIGGER fiscal_envelopes_immutable_payload
BEFORE UPDATE OF tenant_id, taxpayer_rut, kind, document_id, xml_sha256, signed_xml
ON fiscal_envelopes
BEGIN
  SELECT RAISE(ABORT, 'fiscal envelope payload is immutable');
END;

CREATE TRIGGER fiscal_envelopes_no_delete
BEFORE DELETE ON fiscal_envelopes
BEGIN
  SELECT RAISE(ABORT, 'fiscal_envelopes cannot be deleted');
END;

PRAGMA foreign_keys = ON;
