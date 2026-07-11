CREATE TABLE received_document_lines (
    received_document_id TEXT NOT NULL REFERENCES received_fiscal_documents(id),
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    name TEXT NOT NULL,
    quantity TEXT,
    amount INTEGER NOT NULL CHECK (amount >= 0),
    PRIMARY KEY (received_document_id, line_number)
);

CREATE TRIGGER received_lines_no_update BEFORE UPDATE ON received_document_lines
BEGIN SELECT RAISE(ABORT, 'received lines are immutable'); END;
CREATE TRIGGER received_lines_no_delete BEFORE DELETE ON received_document_lines
BEGIN SELECT RAISE(ABORT, 'received lines cannot be deleted'); END;
