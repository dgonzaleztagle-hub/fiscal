CREATE TABLE rcv_purchase_snapshots (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    period TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    source TEXT NOT NULL CHECK (source IN ('official_connector', 'csv_import', 'synthetic')),
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    imported_at TEXT NOT NULL,
    UNIQUE (tenant_id, period, version),
    UNIQUE (tenant_id, period, payload_sha256)
);

CREATE TABLE rcv_purchase_entries (
    id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES rcv_purchase_snapshots(id),
    issuer_rut TEXT NOT NULL,
    document_type INTEGER NOT NULL CHECK (document_type IN (33, 34, 56, 61)),
    folio INTEGER NOT NULL CHECK (folio > 0),
    issued_on TEXT NOT NULL,
    exempt_amount INTEGER NOT NULL CHECK (exempt_amount >= 0),
    net_amount INTEGER NOT NULL CHECK (net_amount >= 0),
    vat_amount INTEGER NOT NULL CHECK (vat_amount >= 0),
    total_amount INTEGER NOT NULL CHECK (total_amount >= 0),
    status TEXT NOT NULL CHECK (status IN ('pending', 'registered', 'claimed', 'excluded')),
    UNIQUE (snapshot_id, issuer_rut, document_type, folio)
);

CREATE TRIGGER rcv_snapshots_no_update BEFORE UPDATE ON rcv_purchase_snapshots
BEGIN SELECT RAISE(ABORT, 'rcv snapshots are immutable'); END;
CREATE TRIGGER rcv_snapshots_no_delete BEFORE DELETE ON rcv_purchase_snapshots
BEGIN SELECT RAISE(ABORT, 'rcv snapshots cannot be deleted'); END;
CREATE TRIGGER rcv_entries_no_update BEFORE UPDATE ON rcv_purchase_entries
BEGIN SELECT RAISE(ABORT, 'rcv entries are immutable'); END;
CREATE TRIGGER rcv_entries_no_delete BEFORE DELETE ON rcv_purchase_entries
BEGIN SELECT RAISE(ABORT, 'rcv entries cannot be deleted'); END;
