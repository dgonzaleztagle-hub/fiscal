from datetime import date, datetime, timezone

import pytest

from completo_dte.adapters.sii import LegacyEnvelopeStatus, LegacyUploadReceipt
from completo_dte.application import (
    InvoiceBatchCoordinator,
    InvoiceEnvelopeWorker,
    IssueInvoiceService,
    SubmitEnvelopeCommand,
)
from completo_dte.domain import EnvelopeAuthorization
from completo_dte.infrastructure import EnvelopeState, FolioLedgerError
from test_issue_invoice import setup_invoice


class FakeLegacyApi:
    def __init__(self, *, upload_error: Exception | None = None, repairs: int = 0):
        self.upload_error = upload_error
        self.repairs = repairs
        self.upload_calls = 0

    def upload(self, _xml, *, issuer_rut, sender_rut, filename):
        self.upload_calls += 1
        if self.upload_error:
            raise self.upload_error
        return LegacyUploadReceipt(
            track_id="INV-456789",
            status="0",
            received_at="2026-07-10 16:00:00",
        )

    def get_upload_status(self, *, issuer_rut, track_id):
        return LegacyEnvelopeStatus(
            track_id=track_id,
            status="EPR",
            reported=1,
            accepted=1,
            rejected=0,
            repairs=self.repairs,
        )


def prepared_invoice(tmp_path, api):
    ledger, caf, caf_id, credential, command = setup_invoice(tmp_path)
    IssueInvoiceService(
        ledger=ledger,
        resolve_caf=lambda requested: caf if requested == caf_id else None,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc),
    ).issue(command)
    coordinator = InvoiceBatchCoordinator(
        ledger=ledger,
        credential=credential,
        authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
        sender_rut="12345678-5",
        clock=lambda: datetime(2026, 7, 10, 15, 40, tzinfo=timezone.utc),
    )
    envelope = coordinator.prepare_dispatch(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
    )
    assert envelope is not None
    assert envelope.kind == "envio_dte"
    assert coordinator.prepare_dispatch(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
    ) is None
    worker = InvoiceEnvelopeWorker(ledger=ledger, api=api)  # type: ignore[arg-type]
    command = SubmitEnvelopeCommand(
        tenant_id="tenant-a",
        envelope_id=envelope.id,
        sender_rut="12345678-5",
        filename="facturas-1.xml",
    )
    return worker, command


def test_invoice_batch_uploads_once_and_reconciles_objections(tmp_path) -> None:
    api = FakeLegacyApi(repairs=1)
    worker, command = prepared_invoice(tmp_path, api)

    submitted = worker.submit(command)
    reconciled = worker.reconcile(tenant_id="tenant-a", envelope_id=submitted.id)

    assert submitted.status is EnvelopeState.SUBMITTED
    assert submitted.track_id == "INV-456789"
    assert reconciled.status is EnvelopeState.ACCEPTED_WITH_OBJECTIONS
    with pytest.raises(FolioLedgerError, match="no debe reenviarse"):
        worker.submit(command)
    assert api.upload_calls == 1


def test_invoice_timeout_is_unknown_and_blocks_blind_retry(tmp_path) -> None:
    api = FakeLegacyApi(upload_error=TimeoutError("corte post-upload"))
    worker, command = prepared_invoice(tmp_path, api)

    unknown = worker.submit(command)

    assert unknown.status is EnvelopeState.UNKNOWN
    with pytest.raises(FolioLedgerError, match="debe reconciliarse"):
        worker.submit(command)
    with pytest.raises(FolioLedgerError, match="no tiene Track ID"):
        worker.reconcile(tenant_id="tenant-a", envelope_id=unknown.id)
    assert api.upload_calls == 1
