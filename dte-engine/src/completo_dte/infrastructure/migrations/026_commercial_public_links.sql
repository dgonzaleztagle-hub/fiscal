CREATE TABLE commercial_public_links(
 id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,commercial_document_id TEXT NOT NULL REFERENCES commercial_documents(id),
 token_sha256 TEXT NOT NULL UNIQUE,purpose TEXT NOT NULL CHECK(purpose='quote_decision'),expires_at TEXT NOT NULL,
 used_at TEXT,decision TEXT CHECK(decision IN('accepted','rejected')),created_at TEXT NOT NULL
);
