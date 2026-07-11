CREATE TABLE IF NOT EXISTS fiscal_envelopes (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    taxpayer_rut TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('envio_boleta', 'rcof')),
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

CREATE INDEX IF NOT EXISTS idx_fiscal_envelopes_pending
ON fiscal_envelopes (status, updated_at);

CREATE TABLE IF NOT EXISTS fiscal_submission_attempts (
    id TEXT PRIMARY KEY,
    envelope_id TEXT NOT NULL REFERENCES fiscal_envelopes(id),
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('started', 'succeeded', 'failed', 'unknown')),
    request_sha256 TEXT NOT NULL,
    track_id TEXT,
    response_code TEXT,
    response_message TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    CHECK (attempt_number >= 1),
    CHECK (length(request_sha256) = 64),
    UNIQUE (envelope_id, attempt_number)
);

CREATE INDEX IF NOT EXISTS idx_submission_attempts_envelope
ON fiscal_submission_attempts (envelope_id, attempt_number);
