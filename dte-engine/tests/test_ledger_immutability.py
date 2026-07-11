import sqlite3

import pytest

from completo_dte.infrastructure import FolioLedger
from test_issue_boleta import setup_issuance


def test_signed_documents_and_events_are_database_immutable(tmp_path) -> None:
    ledger, caf, _caf_id, credential, command = setup_issuance(tmp_path)
    from completo_dte.application import IssueBoletaService

    service = IssueBoletaService(
        ledger=ledger,
        resolve_caf=lambda _requested: caf,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
    )
    record = service.issue(command)
    connection = sqlite3.connect(tmp_path / "issuance.sqlite3")
    try:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE fiscal_documents SET signed_xml = ? WHERE id = ?",
                (b"<altered/>", record.id),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM folio_events")
    finally:
        connection.close()


def test_envelope_payload_cannot_change_but_remote_state_can(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "ledger.sqlite3")
    ledger.migrate()
    envelope = ledger.persist_envelope(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
        kind="rcof",
        document_id="RCOF_1",
        signed_xml=b"<signed/>",
    )
    attempt = ledger.begin_submission(envelope.id)
    from completo_dte.infrastructure import AttemptState

    submitted = ledger.complete_submission(
        attempt.id,
        status=AttemptState.SUCCEEDED,
        track_id="123",
    )
    assert submitted.track_id == "123"

    connection = sqlite3.connect(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE fiscal_envelopes SET signed_xml = ? WHERE id = ?",
                (b"<different/>", envelope.id),
            )
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            connection.execute(
                "DELETE FROM fiscal_envelopes WHERE id = ?",
                (envelope.id,),
            )
    finally:
        connection.close()


def test_migrations_are_versioned_with_content_hash(tmp_path) -> None:
    path = tmp_path / "migrations.sqlite3"
    ledger = FolioLedger(path)
    ledger.migrate()
    ledger.migrate()

    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(
            "SELECT name, sha256 FROM schema_migrations ORDER BY name"
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) >= 6
    assert all(len(digest) == 64 for _name, digest in rows)
