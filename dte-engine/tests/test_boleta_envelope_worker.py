from completo_dte.adapters.sii import (
    RemoteEnvelopeStatus,
    SiiApiError,
    UploadReceipt,
)
from completo_dte.application import BoletaEnvelopeWorker, SubmitEnvelopeCommand
from completo_dte.infrastructure import EnvelopeState, FolioLedger, FolioLedgerError
import pytest


class FakeApi:
    def __init__(self, *, upload_error: Exception | None = None, status: str = "EPR"):
        self.upload_error = upload_error
        self.status = status
        self.upload_calls = 0

    def upload_boletas(self, _xml, *, issuer_rut, sender_rut, filename):
        self.upload_calls += 1
        if self.upload_error:
            raise self.upload_error
        return UploadReceipt(
            issuer_rut=issuer_rut,
            sender_rut=sender_rut,
            track_id="987654",
            received_at="2026-07-09 12:00:00",
            status="REC",
            filename=filename,
        )

    def get_envelope_status(self, *, issuer_rut, track_id):
        return RemoteEnvelopeStatus(
            track_id=track_id,
            status=self.status,
            issuer_rut=issuer_rut,
            sender_rut="12691078-9",
            received_at="2026-07-09 12:00:00",
            statistics=({"aceptados": 2},),
            details=(),
        )


def setup_worker(tmp_path, api):
    ledger = FolioLedger(tmp_path / "worker.sqlite3")
    ledger.migrate()
    envelope = ledger.persist_envelope(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
        kind="envio_boleta",
        document_id="SetBoletas-1",
        signed_xml=b"<EnvioBOLETA firmado='si'/>",
    )
    worker = BoletaEnvelopeWorker(ledger=ledger, api=api)  # type: ignore[arg-type]
    command = SubmitEnvelopeCommand(
        tenant_id="tenant-a",
        envelope_id=envelope.id,
        sender_rut="12691078-9",
        filename="set-boletas-1.xml",
    )
    return ledger, worker, command


def test_worker_persists_track_id_then_reconciles_without_resending(tmp_path) -> None:
    api = FakeApi()
    _ledger, worker, command = setup_worker(tmp_path, api)

    submitted = worker.submit(command)
    accepted = worker.reconcile(tenant_id="tenant-a", envelope_id=submitted.id)

    assert submitted.status is EnvelopeState.SUBMITTED
    assert submitted.track_id == "987654"
    assert accepted.status is EnvelopeState.ACCEPTED
    assert accepted.remote_code == "EPR"
    assert api.upload_calls == 1
    with pytest.raises(FolioLedgerError, match="no debe reenviarse"):
        worker.submit(command)
    assert api.upload_calls == 1


@pytest.mark.parametrize(
    "error",
    [TimeoutError("corte post-upload"), SiiApiError("respuesta ilegible")],
)
def test_ambiguous_upload_is_unknown_and_blocks_blind_retry(tmp_path, error) -> None:
    api = FakeApi(upload_error=error)
    _ledger, worker, command = setup_worker(tmp_path, api)

    unknown = worker.submit(command)

    assert unknown.status is EnvelopeState.UNKNOWN
    with pytest.raises(FolioLedgerError, match="debe reconciliarse"):
        worker.submit(command)
    with pytest.raises(FolioLedgerError, match="no tiene Track ID"):
        worker.reconcile(tenant_id="tenant-a", envelope_id=unknown.id)
    assert api.upload_calls == 1


def test_worker_enforces_tenant_boundary(tmp_path) -> None:
    _ledger, worker, command = setup_worker(tmp_path, FakeApi())
    foreign = SubmitEnvelopeCommand(**{**command.__dict__, "tenant_id": "tenant-b"})
    with pytest.raises(FolioLedgerError, match="tenant"):
        worker.submit(foreign)
