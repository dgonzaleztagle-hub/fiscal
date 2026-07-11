BEGIN;

CREATE SCHEMA IF NOT EXISTS fiscal;
REVOKE ALL ON SCHEMA fiscal FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA fiscal TO service_role;

CREATE TABLE fiscal.issuer_profiles (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    rut text NOT NULL,
    legal_name text NOT NULL,
    business_activity text NOT NULL,
    activity_codes integer[] NOT NULL,
    resolution_date date,
    resolution_number integer,
    software_provider_rut text,
    software_provider_name text,
    environment text NOT NULL CHECK (environment IN ('demo', 'certification', 'production')),
    status text NOT NULL CHECK (status IN ('draft', 'verifying', 'ready', 'suspended')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, rut, environment)
);

CREATE TABLE fiscal.branches (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    issuer_profile_id uuid NOT NULL REFERENCES fiscal.issuer_profiles(id),
    name text NOT NULL,
    sii_branch_code integer,
    address text NOT NULL,
    commune text NOT NULL,
    city text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, issuer_profile_id, name)
);

CREATE TABLE fiscal.credential_bindings (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    issuer_profile_id uuid NOT NULL REFERENCES fiscal.issuer_profiles(id),
    secret_ref text NOT NULL,
    certificate_serial text NOT NULL,
    certificate_subject text NOT NULL,
    fingerprint_sha256 text NOT NULL CHECK (length(fingerprint_sha256) = 64),
    valid_from timestamptz NOT NULL,
    valid_until timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'active', 'expired', 'revoked', 'disabled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (valid_until > valid_from),
    UNIQUE (tenant_id, issuer_profile_id, fingerprint_sha256)
);

CREATE TABLE fiscal.caf_ranges (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    issuer_profile_id uuid NOT NULL REFERENCES fiscal.issuer_profiles(id),
    document_type smallint NOT NULL CHECK (document_type IN (33, 34, 39, 41, 52, 56, 61)),
    folio_from bigint NOT NULL CHECK (folio_from > 0),
    folio_to bigint NOT NULL,
    next_folio bigint NOT NULL,
    authorization_date date NOT NULL,
    caf_sha256 text NOT NULL CHECK (length(caf_sha256) = 64),
    secret_ref text NOT NULL,
    status text NOT NULL CHECK (status IN ('active', 'exhausted', 'annulled', 'disabled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (folio_to >= folio_from),
    CHECK (next_folio >= folio_from AND next_folio <= folio_to + 1),
    UNIQUE (tenant_id, issuer_profile_id, document_type, folio_from, folio_to)
);

CREATE TABLE fiscal.folio_leases (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    issuer_profile_id uuid NOT NULL REFERENCES fiscal.issuer_profiles(id),
    caf_range_id uuid NOT NULL REFERENCES fiscal.caf_ranges(id),
    document_type smallint NOT NULL,
    folio bigint NOT NULL,
    idempotency_key text NOT NULL,
    request_sha256 text NOT NULL CHECK (length(request_sha256) = 64),
    status text NOT NULL CHECK (status IN ('reserved', 'consumed', 'voided')),
    reserved_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, idempotency_key),
    UNIQUE (issuer_profile_id, document_type, folio)
);

CREATE TABLE fiscal.documents (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    issuer_profile_id uuid NOT NULL REFERENCES fiscal.issuer_profiles(id),
    branch_id uuid NOT NULL REFERENCES fiscal.branches(id),
    lease_id uuid NOT NULL UNIQUE REFERENCES fiscal.folio_leases(id),
    document_type smallint NOT NULL CHECK (document_type IN (33, 34, 39, 41, 52, 56, 61)),
    folio bigint NOT NULL,
    issued_on date NOT NULL,
    receiver_rut text,
    canonical_payload jsonb NOT NULL,
    xml_object_key text NOT NULL,
    xml_sha256 text NOT NULL CHECK (length(xml_sha256) = 64),
    public_id text NOT NULL UNIQUE CHECK (length(public_id) >= 32),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (issuer_profile_id, document_type, folio)
);

CREATE TABLE fiscal.document_references (
    document_id uuid NOT NULL REFERENCES fiscal.documents(id),
    line_number smallint NOT NULL CHECK (line_number BETWEEN 1 AND 40),
    referenced_document_id uuid REFERENCES fiscal.documents(id),
    referenced_type text NOT NULL,
    referenced_folio text,
    correction_code smallint CHECK (correction_code IN (1, 2, 3)),
    reason text,
    PRIMARY KEY (document_id, line_number)
);

CREATE TABLE fiscal.document_state (
    document_id uuid PRIMARY KEY REFERENCES fiscal.documents(id),
    status text NOT NULL CHECK (status IN (
        'issued', 'queued', 'submitted', 'accepted', 'accepted_with_objections',
        'rejected', 'unknown'
    )),
    envelope_id uuid,
    track_id text,
    remote_code text,
    remote_message text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fiscal.envelopes (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    issuer_profile_id uuid NOT NULL REFERENCES fiscal.issuer_profiles(id),
    kind text NOT NULL CHECK (kind IN ('envio_boleta', 'envio_dte', 'rcof', 'exchange_response')),
    document_id text NOT NULL,
    xml_object_key text NOT NULL,
    xml_sha256 text NOT NULL CHECK (length(xml_sha256) = 64),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, issuer_profile_id, kind, document_id)
);

ALTER TABLE fiscal.document_state
    ADD CONSTRAINT document_state_envelope_fk
    FOREIGN KEY (envelope_id) REFERENCES fiscal.envelopes(id);

CREATE TABLE fiscal.envelope_documents (
    envelope_id uuid NOT NULL REFERENCES fiscal.envelopes(id),
    document_id uuid NOT NULL REFERENCES fiscal.documents(id),
    ordinal smallint NOT NULL CHECK (ordinal BETWEEN 1 AND 500),
    PRIMARY KEY (envelope_id, document_id),
    UNIQUE (envelope_id, ordinal)
);

CREATE TABLE fiscal.envelope_state (
    envelope_id uuid PRIMARY KEY REFERENCES fiscal.envelopes(id),
    status text NOT NULL CHECK (status IN (
        'prepared', 'submitting', 'submitted', 'accepted',
        'accepted_with_objections', 'rejected', 'unknown'
    )),
    track_id text,
    remote_code text,
    remote_message text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fiscal.submission_attempts (
    id uuid PRIMARY KEY,
    envelope_id uuid NOT NULL REFERENCES fiscal.envelopes(id),
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    request_sha256 text NOT NULL CHECK (length(request_sha256) = 64),
    status text NOT NULL CHECK (status IN ('started', 'succeeded', 'failed', 'unknown')),
    track_id text,
    response_code text,
    response_message text,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    UNIQUE (envelope_id, attempt_number)
);

CREATE TABLE fiscal.inbound_documents (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    issuer_profile_id uuid NOT NULL REFERENCES fiscal.issuer_profiles(id),
    document_type smallint NOT NULL,
    folio bigint NOT NULL,
    issuer_rut text NOT NULL,
    receiver_rut text NOT NULL,
    issued_on date NOT NULL,
    total_amount bigint NOT NULL,
    xml_object_key text NOT NULL,
    xml_sha256 text NOT NULL CHECK (length(xml_sha256) = 64),
    signature_status text NOT NULL CHECK (signature_status IN ('valid', 'invalid', 'unknown')),
    schema_status text NOT NULL CHECK (schema_status IN ('valid', 'invalid', 'unknown')),
    received_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, issuer_rut, document_type, folio)
);

CREATE TABLE fiscal.fiscal_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id uuid NOT NULL,
    aggregate_type text NOT NULL,
    aggregate_id uuid NOT NULL,
    sequence integer NOT NULL CHECK (sequence > 0),
    event_type text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    previous_hash text,
    event_hash text NOT NULL CHECK (length(event_hash) = 64),
    occurred_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (aggregate_type, aggregate_id, sequence)
);

CREATE INDEX fiscal_documents_tenant_date_idx
    ON fiscal.documents (tenant_id, issued_on DESC, created_at DESC);
CREATE INDEX fiscal_document_state_status_idx
    ON fiscal.document_state (status, updated_at);
CREATE INDEX fiscal_caf_allocator_idx
    ON fiscal.caf_ranges (tenant_id, issuer_profile_id, document_type, status, next_folio);
CREATE INDEX fiscal_envelope_state_status_idx
    ON fiscal.envelope_state (status, updated_at);
CREATE INDEX fiscal_inbound_tenant_date_idx
    ON fiscal.inbound_documents (tenant_id, issued_on DESC);

CREATE OR REPLACE FUNCTION fiscal.reject_immutable_change()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is immutable', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER fiscal_documents_immutable
BEFORE UPDATE OR DELETE ON fiscal.documents
FOR EACH ROW EXECUTE FUNCTION fiscal.reject_immutable_change();

CREATE TRIGGER fiscal_envelopes_immutable
BEFORE UPDATE OR DELETE ON fiscal.envelopes
FOR EACH ROW EXECUTE FUNCTION fiscal.reject_immutable_change();

CREATE TRIGGER fiscal_events_immutable
BEFORE UPDATE OR DELETE ON fiscal.fiscal_events
FOR EACH ROW EXECUTE FUNCTION fiscal.reject_immutable_change();

CREATE TRIGGER fiscal_inbound_immutable
BEFORE UPDATE OR DELETE ON fiscal.inbound_documents
FOR EACH ROW EXECUTE FUNCTION fiscal.reject_immutable_change();

REVOKE ALL ON ALL TABLES IN SCHEMA fiscal FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA fiscal FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA fiscal TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA fiscal TO service_role;

COMMIT;
