CREATE TABLE IF NOT EXISTS caf_ranges (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    taxpayer_rut TEXT NOT NULL,
    document_type INTEGER NOT NULL,
    folio_from INTEGER NOT NULL,
    folio_to INTEGER NOT NULL,
    next_folio INTEGER NOT NULL,
    key_id INTEGER NOT NULL,
    imported_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    CHECK (folio_from > 0),
    CHECK (folio_to >= folio_from),
    CHECK (next_folio >= folio_from)
);

CREATE INDEX IF NOT EXISTS idx_caf_ranges_allocator
ON caf_ranges (tenant_id, taxpayer_rut, document_type, active, next_folio);

CREATE TABLE IF NOT EXISTS folio_leases (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    taxpayer_rut TEXT NOT NULL,
    document_type INTEGER NOT NULL,
    folio INTEGER NOT NULL,
    caf_range_id TEXT NOT NULL REFERENCES caf_ranges(id),
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('reserved', 'consumed', 'voided')),
    document_id TEXT,
    void_reason TEXT,
    reserved_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (taxpayer_rut, document_type, folio),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS folio_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_id TEXT NOT NULL REFERENCES folio_leases(id),
    event_type TEXT NOT NULL CHECK (event_type IN ('reserved', 'consumed', 'voided')),
    occurred_at TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_folio_events_lease
ON folio_events (lease_id, sequence);

