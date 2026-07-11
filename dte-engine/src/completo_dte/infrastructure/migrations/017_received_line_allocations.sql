CREATE TABLE received_line_allocations (
    classification_id TEXT NOT NULL REFERENCES received_document_classifications(id),
    line_number INTEGER NOT NULL,
    destination TEXT NOT NULL CHECK (destination IN ('expense', 'inventory', 'fixed_asset')),
    control_plane_ref TEXT,
    PRIMARY KEY (classification_id, line_number)
);

CREATE TRIGGER received_line_allocations_no_update BEFORE UPDATE ON received_line_allocations
BEGIN SELECT RAISE(ABORT, 'received line allocations are immutable'); END;
CREATE TRIGGER received_line_allocations_no_delete BEFORE DELETE ON received_line_allocations
BEGIN SELECT RAISE(ABORT, 'received line allocations cannot be deleted'); END;
