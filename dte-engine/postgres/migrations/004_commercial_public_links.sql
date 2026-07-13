CREATE TABLE fiscal.commercial_public_links(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,commercial_document_id uuid NOT NULL REFERENCES fiscal.commercial_documents(id),token_sha256 char(64) NOT NULL UNIQUE,purpose text NOT NULL CHECK(purpose='quote_decision'),expires_at timestamptz NOT NULL,used_at timestamptz,decision text CHECK(decision IN('accepted','rejected')),created_at timestamptz NOT NULL DEFAULT now());
ALTER TABLE fiscal.commercial_public_links ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON fiscal.commercial_public_links FROM anon,authenticated;
