import pytest

from completo_dte.infrastructure import (
    AttemptState,
    EnvelopeState,
    FolioLedger,
    FolioLedgerError,
)


def test_persists_envelope_and_track_id_without_blind_resubmission(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "transmission.sqlite3")
    ledger.migrate()
    envelope = ledger.persist_envelope(
        tenant_id="restaurant-1",
        taxpayer_rut="12345678-5",
        kind="envio_boleta",
        document_id="SetDoc",
        signed_xml=b"<signed-envelope/>",
    )
    assert envelope.status == EnvelopeState.PREPARED

    same = ledger.persist_envelope(
        tenant_id="restaurant-1",
        taxpayer_rut="12345678-5",
        kind="envio_boleta",
        document_id="SetDoc",
        signed_xml=b"<signed-envelope/>",
    )
    assert same.id == envelope.id

    attempt = ledger.begin_submission(envelope.id)
    assert attempt.attempt_number == 1
    assert ledger.begin_submission(envelope.id).id == attempt.id

    submitted = ledger.complete_submission(
        attempt.id,
        status=AttemptState.SUCCEEDED,
        track_id="1234567890",
        response_code="0",
        response_message="RECIBIDO",
    )
    assert submitted.status == EnvelopeState.SUBMITTED
    assert submitted.track_id == "1234567890"
    with pytest.raises(FolioLedgerError, match="no debe reenviarse"):
        ledger.begin_submission(envelope.id)

    accepted = ledger.update_remote_state(
        envelope.id,
        status=EnvelopeState.ACCEPTED,
        remote_code="EPR",
        remote_message="ENVIO PROCESADO",
    )
    assert accepted.status == EnvelopeState.ACCEPTED


def test_unknown_result_requires_reconciliation_before_retry(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "unknown.sqlite3")
    ledger.migrate()
    envelope = ledger.persist_envelope(
        tenant_id="restaurant-1",
        taxpayer_rut="12345678-5",
        kind="rcof",
        document_id="RCOF_20260709",
        signed_xml=b"<signed-rcof/>",
    )
    attempt = ledger.begin_submission(envelope.id)
    unknown = ledger.complete_submission(
        attempt.id,
        status=AttemptState.UNKNOWN,
        response_message="Timeout después de transmitir",
    )
    assert unknown.status == EnvelopeState.UNKNOWN

    with pytest.raises(FolioLedgerError, match="debe reconciliarse"):
        ledger.begin_submission(envelope.id)


def test_rejects_same_envelope_id_with_changed_xml(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "changed.sqlite3")
    ledger.migrate()
    ledger.persist_envelope(
        tenant_id="restaurant-1",
        taxpayer_rut="12345678-5",
        kind="envio_boleta",
        document_id="SetDoc",
        signed_xml=b"<one/>",
    )
    with pytest.raises(FolioLedgerError, match="contenido diferente"):
        ledger.persist_envelope(
            tenant_id="restaurant-1",
            taxpayer_rut="12345678-5",
            kind="envio_boleta",
            document_id="SetDoc",
            signed_xml=b"<two/>",
        )
