from datetime import date

import pytest

from completo_dte.adapters.sii import LegacyEnvelopeStatus, LegacyUploadReceipt
from completo_dte.application import RcofEnvelopeWorker, SubmitRcofCommand
from completo_dte.infrastructure import EnvelopeState, FolioLedgerError
from test_boleta_batch_coordinator import setup_documents


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
            track_id="456789",
            status="0",
            received_at="2026-07-10 12:00:00",
        )

    def get_upload_status(self, *, issuer_rut, track_id):
        return LegacyEnvelopeStatus(
            track_id=track_id,
            status="EPR",
            reported=2,
            accepted=2,
            rejected=0,
            repairs=self.repairs,
        )


def prepared_rcof(tmp_path, api):
    ledger, coordinator, _affected, _exempt = setup_documents(tmp_path)
    envelope = coordinator.prepare_daily_summary(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
        issued_on=date(2026, 7, 10),
    )
    assert envelope is not None
    worker = RcofEnvelopeWorker(ledger=ledger, api=api)  # type: ignore[arg-type]
    command = SubmitRcofCommand(
        tenant_id="tenant-a",
        envelope_id=envelope.id,
        sender_rut="12345678-5",
        filename="rcof-20260710.xml",
    )
    return worker, command


def test_rcof_worker_tracks_upload_and_objections(tmp_path) -> None:
    api = FakeLegacyApi(repairs=1)
    worker, command = prepared_rcof(tmp_path, api)

    submitted = worker.submit(command)
    reconciled = worker.reconcile(
        tenant_id="tenant-a",
        envelope_id=submitted.id,
    )

    assert submitted.status is EnvelopeState.SUBMITTED
    assert submitted.track_id == "456789"
    assert reconciled.status is EnvelopeState.ACCEPTED_WITH_OBJECTIONS
    assert "reparos=1" in (reconciled.remote_message or "")
    with pytest.raises(FolioLedgerError, match="no debe reenviarse"):
        worker.submit(command)
    assert api.upload_calls == 1


def test_rcof_timeout_is_unknown_and_never_retried_blindly(tmp_path) -> None:
    api = FakeLegacyApi(upload_error=TimeoutError("corte post-upload"))
    worker, command = prepared_rcof(tmp_path, api)

    unknown = worker.submit(command)

    assert unknown.status is EnvelopeState.UNKNOWN
    with pytest.raises(FolioLedgerError, match="debe reconciliarse"):
        worker.submit(command)
    with pytest.raises(FolioLedgerError, match="no tiene Track ID"):
        worker.reconcile(tenant_id="tenant-a", envelope_id=unknown.id)
    assert api.upload_calls == 1
