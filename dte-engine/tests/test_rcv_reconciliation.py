from datetime import date

from completo_dte.application import RcvDifferenceType, RcvReconciliationService
from completo_dte.domain import (
    DocumentType,
    RcvPeriod,
    RcvPurchaseEntry,
    RcvPurchaseStatus,
)
from completo_dte.infrastructure import FolioLedger, RcvRepository
from test_received_ledger import received_document


def test_reconciliation_reports_match_mismatch_and_missing_sides(tmp_path) -> None:
    database = tmp_path / "reconcile.sqlite3"
    ledger = FolioLedger(database)
    ledger.migrate()
    received = received_document()
    ledger.import_received_document(
        tenant_id="tenant-a", document=received, source="upload"
    )
    repository = RcvRepository(database)
    entries = (
        RcvPurchaseEntry(
            issuer_rut=received.issuer_rut,
            document_type=received.document_type,
            folio=received.folio,
            issued_on=received.issued_on,
            exempt_amount=0,
            net_amount=18000,
            vat_amount=3420,
            total_amount=21420,
            status=RcvPurchaseStatus.REGISTERED,
        ),
        RcvPurchaseEntry(
            issuer_rut="22222222-2",
            document_type=DocumentType.FACTURA_EXENTA,
            folio=9,
            issued_on=date(2026, 7, 5),
            exempt_amount=5000,
            net_amount=0,
            vat_amount=0,
            total_amount=5000,
            status=RcvPurchaseStatus.REGISTERED,
        ),
    )
    snapshot = repository.import_snapshot(
        tenant_id="tenant-a",
        period=RcvPeriod(2026, 7),
        entries=entries,
        source="synthetic",
    )
    differences = RcvReconciliationService(
        ledger=ledger, repository=repository
    ).reconcile(tenant_id="tenant-a", snapshot=snapshot)

    assert [difference.kind for difference in differences] == [
        RcvDifferenceType.MATCH,
        RcvDifferenceType.ONLY_RCV,
    ]


def test_reconciliation_never_crosses_tenants(tmp_path) -> None:
    database = tmp_path / "reconcile.sqlite3"
    ledger = FolioLedger(database)
    ledger.migrate()
    received = received_document()
    ledger.import_received_document(
        tenant_id="tenant-a", document=received, source="upload"
    )
    repository = RcvRepository(database)
    snapshot = repository.import_snapshot(
        tenant_id="tenant-b",
        period=RcvPeriod(2026, 7),
        entries=(),
        source="synthetic",
    )
    result = RcvReconciliationService(
        ledger=ledger, repository=repository
    ).reconcile(tenant_id="tenant-b", snapshot=snapshot)
    assert result == ()
