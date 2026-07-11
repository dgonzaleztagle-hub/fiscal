from datetime import datetime, timezone

import pytest

from completo_dte.application import IssueInvoiceService
from completo_dte.infrastructure import BackupError, FolioLedger, SqliteBackupService
from test_issue_invoice import setup_invoice


def test_backup_restore_preserves_immutable_document_and_events(tmp_path) -> None:
    ledger, caf, _caf_id, credential, command = setup_invoice(tmp_path)
    issued = IssueInvoiceService(
        ledger=ledger,
        resolve_caf=lambda _requested: caf,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc),
    ).issue(command)
    source = tmp_path / "invoices.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    service = SqliteBackupService()
    manifest = service.backup(source, backup)
    service.restore(backup, restored, manifest)

    restored_ledger = FolioLedger(restored)
    document = restored_ledger.document_by_id(issued.id, tenant_id="tenant-a")
    assert document == issued
    assert [event["event_type"] for event in restored_ledger.events(issued.lease_id)] == [
        "reserved",
        "consumed",
    ]
    assert manifest.integrity == "ok"


def test_restore_rejects_tampered_manifest_without_overwriting_target(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "source.sqlite3")
    ledger.migrate()
    service = SqliteBackupService()
    manifest = service.backup(tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3")
    broken = manifest.__class__(**{**manifest.__dict__, "database_sha256": "0" * 64})
    with pytest.raises(BackupError, match="manifiesto"):
        service.restore(tmp_path / "backup.sqlite3", tmp_path / "target.sqlite3", broken)
    assert not (tmp_path / "target.sqlite3").exists()
