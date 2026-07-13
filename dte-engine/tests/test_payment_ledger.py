import pytest

from completo_dte.infrastructure import FolioLedger, FolioLedgerError


def values(reference="ref-1", amount=11900):
    return dict(
        tenant_id="tenant-a", provider="Transbank", terminal_id="POS-1",
        authorization_code="AUTH-1", provider_reference=reference,
        sale_ref="sale-1", amount=amount,
        occurred_at="2026-07-12T13:00:00-04:00", settlement_ref="settle-1",
        source="provider_import",
    )


def test_payment_import_is_idempotent_and_tenant_scoped(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "db.sqlite3")
    ledger.migrate()
    first = ledger.import_electronic_payment(**values())
    retry = ledger.import_electronic_payment(**values())
    assert retry.id == first.id
    assert len(ledger.list_electronic_payments(tenant_id="tenant-a", period="2026-07")) == 1
    assert ledger.list_electronic_payments(tenant_id="tenant-b", period="2026-07") == ()
    with pytest.raises(FolioLedgerError, match="contenido diferente"):
        ledger.import_electronic_payment(**values(amount=12000))


def test_reconciliation_snapshot_is_versioned_and_idempotent(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "db.sqlite3")
    ledger.migrate()
    first = ledger.persist_payment_reconciliation(
        tenant_id="tenant-a", period="2026-07", payload={"ready": True}
    )
    retry = ledger.persist_payment_reconciliation(
        tenant_id="tenant-a", period="2026-07", payload={"ready": True}
    )
    second = ledger.persist_payment_reconciliation(
        tenant_id="tenant-a", period="2026-07", payload={"ready": False}
    )
    assert retry.id == first.id
    assert second.version == 2
    assert ledger.latest_payment_reconciliation(
        tenant_id="tenant-a", period="2026-07"
    ).id == second.id
