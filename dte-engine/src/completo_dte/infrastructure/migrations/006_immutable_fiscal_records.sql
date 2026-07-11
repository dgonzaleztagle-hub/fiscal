CREATE TRIGGER fiscal_documents_no_update
BEFORE UPDATE ON fiscal_documents
BEGIN
  SELECT RAISE(ABORT, 'fiscal_documents are immutable');
END;

CREATE TRIGGER fiscal_documents_no_delete
BEFORE DELETE ON fiscal_documents
BEGIN
  SELECT RAISE(ABORT, 'fiscal_documents are immutable');
END;

CREATE TRIGGER folio_events_no_update
BEFORE UPDATE ON folio_events
BEGIN
  SELECT RAISE(ABORT, 'folio_events are append-only');
END;

CREATE TRIGGER folio_events_no_delete
BEFORE DELETE ON folio_events
BEGIN
  SELECT RAISE(ABORT, 'folio_events are append-only');
END;

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

CREATE TRIGGER submission_attempts_immutable_identity
BEFORE UPDATE OF envelope_id, attempt_number, request_sha256, started_at
ON fiscal_submission_attempts
BEGIN
  SELECT RAISE(ABORT, 'submission attempt identity is immutable');
END;

CREATE TRIGGER submission_attempts_no_delete
BEFORE DELETE ON fiscal_submission_attempts
BEGIN
  SELECT RAISE(ABORT, 'submission attempts cannot be deleted');
END;
