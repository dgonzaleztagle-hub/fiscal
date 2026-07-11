CREATE TABLE fiscal_document_corrections (
    source_document_id TEXT PRIMARY KEY REFERENCES fiscal_documents(id),
    target_document_id TEXT NOT NULL REFERENCES fiscal_documents(id),
    correction_code INTEGER NOT NULL CHECK (correction_code IN (1, 2, 3)),
    applied_amount INTEGER NOT NULL CHECK (applied_amount >= 0),
    created_at TEXT NOT NULL,
    CHECK (source_document_id <> target_document_id)
);

CREATE INDEX idx_document_corrections_target
ON fiscal_document_corrections (target_document_id, correction_code);

CREATE TRIGGER fiscal_document_corrections_no_update
BEFORE UPDATE ON fiscal_document_corrections
BEGIN
  SELECT RAISE(ABORT, 'fiscal document corrections are immutable');
END;

CREATE TRIGGER fiscal_document_corrections_no_delete
BEFORE DELETE ON fiscal_document_corrections
BEGIN
  SELECT RAISE(ABORT, 'fiscal document corrections cannot be deleted');
END;
