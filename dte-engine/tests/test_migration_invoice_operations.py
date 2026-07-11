from datetime import datetime, timezone
import hashlib
from importlib.resources import files
import sqlite3

from completo_dte.infrastructure import FolioLedger


def test_existing_boleta_ledger_upgrades_without_losing_envelopes(tmp_path) -> None:
    database = tmp_path / "existing.sqlite3"
    migrations = files("completo_dte.infrastructure").joinpath("migrations")
    connection = sqlite3.connect(database)
    connection.execute(
        """
        CREATE TABLE schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL,
            sha256 TEXT
        )
        """
    )
    for migration in sorted(
        item for item in migrations.iterdir()
        if item.name.endswith(".sql") and item.name < "008_invoice_envelopes.sql"
    ):
        source = migration.read_bytes()
        connection.executescript(source.decode("utf-8"))
        connection.execute(
            "INSERT INTO schema_migrations VALUES (?, ?, ?)",
            (
                migration.name,
                datetime.now(timezone.utc).isoformat(),
                hashlib.sha256(source).hexdigest(),
            ),
        )
    payload = b"<EnvioBOLETA firmado='si'/>"
    connection.execute(
        """
        INSERT INTO fiscal_envelopes (
            id, tenant_id, taxpayer_rut, kind, document_id, xml_sha256,
            signed_xml, status, created_at, updated_at
        ) VALUES ('old-envelope', 'tenant-a', '12345678-5', 'envio_boleta',
                  'SetOld', ?, ?, 'accepted', ?, ?)
        """,
        (
            hashlib.sha256(payload).hexdigest(),
            payload,
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    connection.commit()
    connection.close()

    ledger = FolioLedger(database)
    ledger.migrate()

    preserved = ledger.envelope_by_id("old-envelope", tenant_id="tenant-a")
    assert preserved is not None
    assert preserved.signed_xml == payload
    invoice = ledger.persist_envelope(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
        kind="envio_dte",
        document_id="SetInvoices",
        signed_xml=b"<EnvioDTE firmado='si'/>",
    )
    assert invoice.kind == "envio_dte"
