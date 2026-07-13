CREATE TABLE commercial_documents (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('quote','sales_order','purchase_order')),
    number INTEGER NOT NULL,
    branch_id TEXT NOT NULL,
    counterparty_ref TEXT NOT NULL,
    counterparty_name TEXT NOT NULL,
    issued_on TEXT NOT NULL,
    valid_until TEXT,
    currency TEXT NOT NULL CHECK (currency = 'CLP'),
    status TEXT NOT NULL CHECK (status IN ('draft','sent','accepted','rejected','cancelled','converted')),
    notes TEXT NOT NULL DEFAULT '',
    total INTEGER NOT NULL CHECK (total >= 0),
    idempotency_key TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    converted_document_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (tenant_id, kind, number),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE commercial_document_lines (
    id TEXT PRIMARY KEY,
    commercial_document_id TEXT NOT NULL REFERENCES commercial_documents(id),
    line_number INTEGER NOT NULL,
    product_ref TEXT,
    description TEXT NOT NULL,
    quantity TEXT NOT NULL,
    unit_price TEXT NOT NULL,
    discount_percent TEXT NOT NULL,
    subtotal INTEGER NOT NULL CHECK (subtotal >= 0),
    UNIQUE (commercial_document_id, line_number)
);

CREATE TABLE commercial_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    commercial_document_id TEXT NOT NULL REFERENCES commercial_documents(id),
    event_type TEXT NOT NULL,
    actor_ref TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    occurred_at TEXT NOT NULL
);

CREATE INDEX idx_commercial_documents_tenant_status
ON commercial_documents (tenant_id, kind, status, issued_on DESC);
