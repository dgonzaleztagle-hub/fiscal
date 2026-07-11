from datetime import date

import pytest

from completo_dte.domain import (
    DocumentType,
    RcvError,
    RcvPeriod,
    RcvPurchaseEntry,
    RcvPurchaseStatus,
)
from completo_dte.infrastructure import FolioLedger, FolioLedgerError, RcvRepository


def entry(total=11900):
    return RcvPurchaseEntry(
        issuer_rut="12345678-5",
        document_type=DocumentType.FACTURA_AFECTA,
        folio=7,
        issued_on=date(2026, 7, 10),
        exempt_amount=0,
        net_amount=10000,
        vat_amount=1900,
        total_amount=total,
        status=RcvPurchaseStatus.REGISTERED,
    )


def test_snapshot_is_idempotent_versioned_and_tenant_isolated(tmp_path) -> None:
    database = tmp_path / "rcv.sqlite3"
    FolioLedger(database).migrate()
    repository = RcvRepository(database)
    period = RcvPeriod(2026, 7)
    first = repository.import_snapshot(
        tenant_id="tenant-a", period=period, entries=(entry(),), source="synthetic"
    )
    retry = repository.import_snapshot(
        tenant_id="tenant-a", period=period, entries=(entry(),), source="csv_import"
    )
    changed_entry = entry().__class__(
        **{**entry().__dict__, "status": RcvPurchaseStatus.CLAIMED}
    )
    second = repository.import_snapshot(
        tenant_id="tenant-a",
        period=period,
        entries=(changed_entry,),
        source="synthetic",
    )

    assert retry == first
    assert first.version == 1
    assert second.version == 2
    assert repository.latest_snapshot(tenant_id="tenant-a", period=period) == second
    assert repository.latest_snapshot(tenant_id="tenant-b", period=period) is None
    assert repository.entries(first.id, tenant_id="tenant-b") == []
    assert repository.entries(first.id, tenant_id="tenant-a")[0].entry == entry()


def test_duplicate_identity_in_one_snapshot_is_rejected(tmp_path) -> None:
    database = tmp_path / "rcv.sqlite3"
    FolioLedger(database).migrate()
    with pytest.raises(FolioLedgerError, match="duplicados"):
        RcvRepository(database).import_snapshot(
            tenant_id="tenant-a",
            period=RcvPeriod(2026, 7),
            entries=(entry(), entry()),
            source="synthetic",
        )


def test_rcv_totals_must_balance() -> None:
    with pytest.raises(RcvError, match="no coincide"):
        entry(total=12000)
