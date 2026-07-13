import json
import sqlite3

import pytest

from completo_dte.infrastructure import FolioLedger


def test_monthly_close_storage_is_private_by_tenant_and_immutable(tmp_path) -> None:
    database = tmp_path / "fiscal.sqlite3"
    ledger = FolioLedger(database)
    ledger.migrate()
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO monthly_close_snapshots (
                id, tenant_id, period, version, formula_version, source_sha256,
                calculation_sha256, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "snapshot-a",
                "tenant-a",
                "2026-07",
                1,
                "plus-baseline-2026-07-v1",
                "a" * 64,
                "b" * 64,
                json.dumps({"total_payable": 100}),
                "2026-07-12T10:00:00Z",
            ),
        )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE monthly_close_snapshots SET payload_json = '{}' WHERE id = ?",
                ("snapshot-a",),
            )
        row = connection.execute(
            "SELECT tenant_id, period, version FROM monthly_close_snapshots WHERE id = ?",
            ("snapshot-a",),
        ).fetchone()
    assert row == ("tenant-a", "2026-07", 1)
