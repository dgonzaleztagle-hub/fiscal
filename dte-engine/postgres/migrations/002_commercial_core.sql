CREATE TABLE fiscal.commercial_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  kind text NOT NULL CHECK (kind IN ('quote','sales_order','purchase_order')),
  number bigint NOT NULL,
  branch_id uuid NOT NULL,
  counterparty_ref text NOT NULL,
  counterparty_name text NOT NULL,
  issued_on date NOT NULL,
  valid_until date,
  currency char(3) NOT NULL DEFAULT 'CLP',
  status text NOT NULL CHECK (status IN ('draft','sent','accepted','rejected','cancelled','converted')),
  notes text NOT NULL DEFAULT '', total bigint NOT NULL CHECK (total >= 0),
  idempotency_key text NOT NULL, request_sha256 char(64) NOT NULL,
  converted_document_id uuid, created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, kind, number), UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX commercial_documents_tenant_status_idx
  ON fiscal.commercial_documents (tenant_id, kind, status, issued_on DESC);
CREATE TABLE fiscal.commercial_document_lines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  commercial_document_id uuid NOT NULL REFERENCES fiscal.commercial_documents(id),
  line_number integer NOT NULL, product_ref text, description text NOT NULL,
  quantity numeric(18,6) NOT NULL CHECK (quantity > 0),
  unit_price numeric(18,4) NOT NULL CHECK (unit_price >= 0),
  discount_percent numeric(7,4) NOT NULL DEFAULT 0,
  subtotal bigint NOT NULL CHECK (subtotal >= 0),
  UNIQUE (commercial_document_id, line_number)
);
ALTER TABLE fiscal.commercial_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE fiscal.commercial_document_lines ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON fiscal.commercial_documents, fiscal.commercial_document_lines FROM anon, authenticated;
