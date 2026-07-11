CREATE TABLE issuer_credential_references (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    taxpayer_rut TEXT NOT NULL,
    vault_ref TEXT NOT NULL,
    certificate_sha256 TEXT NOT NULL CHECK (length(certificate_sha256) = 64),
    active_from TEXT NOT NULL,
    retired_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (tenant_id, taxpayer_rut, certificate_sha256)
);

CREATE UNIQUE INDEX idx_one_active_issuer_credential
ON issuer_credential_references (tenant_id, taxpayer_rut)
WHERE retired_at IS NULL;

CREATE TRIGGER credential_reference_immutable
BEFORE UPDATE OF tenant_id,taxpayer_rut,vault_ref,certificate_sha256,active_from,created_at
ON issuer_credential_references
BEGIN SELECT RAISE(ABORT, 'credential identity is immutable'); END;

CREATE TRIGGER credential_reference_no_delete BEFORE DELETE ON issuer_credential_references
BEGIN SELECT RAISE(ABORT, 'credential references cannot be deleted'); END;
