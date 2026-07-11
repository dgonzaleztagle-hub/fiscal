CREATE TABLE IF NOT EXISTS fiscal_envelope_documents (
    envelope_id TEXT NOT NULL REFERENCES fiscal_envelopes(id),
    document_record_id TEXT NOT NULL REFERENCES fiscal_documents(id),
    relation_kind TEXT NOT NULL CHECK (relation_kind IN ('dispatch', 'consumption')),
    position INTEGER NOT NULL CHECK (position >= 1),
    created_at TEXT NOT NULL,
    PRIMARY KEY (envelope_id, document_record_id, relation_kind),
    UNIQUE (document_record_id, relation_kind),
    UNIQUE (envelope_id, relation_kind, position)
);

CREATE INDEX IF NOT EXISTS idx_envelope_documents_envelope
ON fiscal_envelope_documents (envelope_id, relation_kind, position);

CREATE TRIGGER fiscal_envelope_documents_no_update
BEFORE UPDATE ON fiscal_envelope_documents
BEGIN
  SELECT RAISE(ABORT, 'fiscal_envelope_documents are immutable');
END;

CREATE TRIGGER fiscal_envelope_documents_no_delete
BEFORE DELETE ON fiscal_envelope_documents
BEGIN
  SELECT RAISE(ABORT, 'fiscal_envelope_documents cannot be deleted');
END;
