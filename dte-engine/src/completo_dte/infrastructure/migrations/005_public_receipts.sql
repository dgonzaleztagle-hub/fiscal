ALTER TABLE fiscal_documents ADD COLUMN public_id TEXT;

UPDATE fiscal_documents
SET public_id = lower(hex(randomblob(16)))
WHERE public_id IS NULL;

CREATE UNIQUE INDEX idx_fiscal_documents_public_id
ON fiscal_documents (public_id);
