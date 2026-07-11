CREATE TABLE received_document_decisions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    received_document_id TEXT NOT NULL REFERENCES received_fiscal_documents(id),
    decision TEXT NOT NULL CHECK (decision IN ('accept_content', 'ack_receipt', 'claim_content', 'claim_partial_delivery', 'claim_total_delivery')),
    reason TEXT,
    status TEXT NOT NULL CHECK (status IN ('prepared', 'submitting', 'confirmed', 'rejected', 'unknown')),
    remote_code TEXT,
    remote_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (received_document_id, decision)
);

CREATE TABLE received_decision_attempts (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES received_document_decisions(id),
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    status TEXT NOT NULL CHECK (status IN ('started', 'succeeded', 'failed', 'unknown')),
    request_sha256 TEXT NOT NULL CHECK (length(request_sha256) = 64),
    remote_code TEXT,
    remote_message TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE (decision_id, attempt_number)
);

CREATE INDEX idx_received_decisions_pending
ON received_document_decisions (tenant_id, status, updated_at);

CREATE TRIGGER received_decisions_immutable_intent
BEFORE UPDATE OF tenant_id, received_document_id, decision, reason, created_at
ON received_document_decisions
BEGIN
  SELECT RAISE(ABORT, 'received decision intent is immutable');
END;

CREATE TRIGGER received_decisions_no_delete
BEFORE DELETE ON received_document_decisions
BEGIN
  SELECT RAISE(ABORT, 'received decisions cannot be deleted');
END;

CREATE TRIGGER received_decision_attempts_immutable_request
BEFORE UPDATE OF decision_id, attempt_number, request_sha256, started_at
ON received_decision_attempts
BEGIN
  SELECT RAISE(ABORT, 'received decision attempt request is immutable');
END;

CREATE TRIGGER received_decision_attempts_no_delete
BEFORE DELETE ON received_decision_attempts
BEGIN
  SELECT RAISE(ABORT, 'received decision attempts cannot be deleted');
END;
