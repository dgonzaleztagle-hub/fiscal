CREATE TABLE consumed_sso_nonces (
    nonce TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    destination TEXT NOT NULL,
    consumed_at TEXT NOT NULL
);

CREATE TRIGGER consumed_sso_nonces_no_update BEFORE UPDATE ON consumed_sso_nonces
BEGIN SELECT RAISE(ABORT, 'consumed sso nonces are immutable'); END;
CREATE TRIGGER consumed_sso_nonces_no_delete BEFORE DELETE ON consumed_sso_nonces
BEGIN SELECT RAISE(ABORT, 'consumed sso nonces cannot be deleted'); END;
