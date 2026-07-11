"""Worker durable para subir y reconciliar sobres de boletas."""

from __future__ import annotations

from dataclasses import dataclass

from completo_dte.adapters.sii import (
    EnvelopeOutcome,
    SiiApiError,
    SiiBoletaApi,
    SiiLegacyDteApi,
)
from completo_dte.infrastructure import (
    AttemptState,
    EnvelopeState,
    FiscalEnvelopeRecord,
    FolioLedger,
    FolioLedgerError,
)


@dataclass(frozen=True)
class SubmitEnvelopeCommand:
    tenant_id: str
    envelope_id: str
    sender_rut: str
    filename: str


@dataclass(frozen=True)
class SubmitRcofCommand:
    tenant_id: str
    envelope_id: str
    sender_rut: str
    filename: str


class BoletaEnvelopeWorker:
    """Mantiene separado el sobre inmutable de cada intento de red."""

    def __init__(self, *, ledger: FolioLedger, api: SiiBoletaApi) -> None:
        self._ledger = ledger
        self._api = api

    def submit(self, command: SubmitEnvelopeCommand) -> FiscalEnvelopeRecord:
        envelope = self._required_envelope(command)
        attempt = self._ledger.begin_submission(envelope.id)
        try:
            receipt = self._api.upload_boletas(
                envelope.signed_xml,
                issuer_rut=envelope.taxpayer_rut,
                sender_rut=command.sender_rut,
                filename=command.filename,
            )
        except SiiApiError as exc:
            # El error puede ocurrir después de que el SII recibió bytes. Sin Track ID
            # no hay evidencia suficiente para declarar un fallo seguro o reenviar.
            return self._ledger.complete_submission(
                attempt.id,
                status=AttemptState.UNKNOWN,
                response_message=str(exc),
            )
        except Exception as exc:
            # Timeouts y cortes de transporte son ambiguos por definición.
            return self._ledger.complete_submission(
                attempt.id,
                status=AttemptState.UNKNOWN,
                response_message=f"{type(exc).__name__}: {exc}",
            )
        return self._ledger.complete_submission(
            attempt.id,
            status=AttemptState.SUCCEEDED,
            track_id=receipt.track_id,
            response_code=receipt.status,
            response_message=f"SII recibió {receipt.filename} el {receipt.received_at}",
        )

    def reconcile(self, *, tenant_id: str, envelope_id: str) -> FiscalEnvelopeRecord:
        envelope = self._ledger.envelope_by_id(envelope_id, tenant_id=tenant_id)
        if envelope is None:
            raise FolioLedgerError("El sobre no existe para el tenant")
        if not envelope.track_id:
            raise FolioLedgerError(
                "El sobre no tiene Track ID; requiere conciliación operativa asistida"
            )
        status = self._api.get_envelope_status(
            issuer_rut=envelope.taxpayer_rut,
            track_id=envelope.track_id,
        )
        state = {
            EnvelopeOutcome.PROCESSING: EnvelopeState.SUBMITTED,
            EnvelopeOutcome.ACCEPTED: EnvelopeState.ACCEPTED,
            EnvelopeOutcome.ACCEPTED_WITH_OBJECTIONS: EnvelopeState.ACCEPTED_WITH_OBJECTIONS,
            EnvelopeOutcome.REJECTED: EnvelopeState.REJECTED,
            EnvelopeOutcome.UNKNOWN: EnvelopeState.UNKNOWN,
        }[status.outcome]
        return self._ledger.update_remote_state(
            envelope.id,
            status=state,
            remote_code=status.status,
            remote_message=status.outcome.value,
        )

    def _required_envelope(
        self,
        command: SubmitEnvelopeCommand,
    ) -> FiscalEnvelopeRecord:
        envelope = self._ledger.envelope_by_id(
            command.envelope_id,
            tenant_id=command.tenant_id,
        )
        if envelope is None:
            raise FolioLedgerError("El sobre no existe para el tenant")
        if envelope.kind != "envio_boleta":
            raise FolioLedgerError("El worker de boletas no admite este tipo de sobre")
        return envelope


class RcofEnvelopeWorker:
    """Sube y reconcilia RCOF por el gateway DTE heredado."""

    def __init__(self, *, ledger: FolioLedger, api: SiiLegacyDteApi) -> None:
        self._ledger = ledger
        self._api = api

    def submit(self, command: SubmitRcofCommand) -> FiscalEnvelopeRecord:
        envelope = self._required_envelope(command.tenant_id, command.envelope_id)
        attempt = self._ledger.begin_submission(envelope.id)
        try:
            receipt = self._api.upload(
                envelope.signed_xml,
                issuer_rut=envelope.taxpayer_rut,
                sender_rut=command.sender_rut,
                filename=command.filename,
            )
        except Exception as exc:
            return self._ledger.complete_submission(
                attempt.id,
                status=AttemptState.UNKNOWN,
                response_message=f"{type(exc).__name__}: {exc}",
            )
        return self._ledger.complete_submission(
            attempt.id,
            status=AttemptState.SUCCEEDED,
            track_id=receipt.track_id,
            response_code=receipt.status,
            response_message=(
                f"SII recibió RCOF el {receipt.received_at}"
                if receipt.received_at
                else "SII recibió RCOF"
            ),
        )

    def reconcile(self, *, tenant_id: str, envelope_id: str) -> FiscalEnvelopeRecord:
        envelope = self._required_envelope(tenant_id, envelope_id)
        if not envelope.track_id:
            raise FolioLedgerError(
                "El RCOF no tiene Track ID; requiere conciliación operativa asistida"
            )
        status = self._api.get_upload_status(
            issuer_rut=envelope.taxpayer_rut,
            track_id=envelope.track_id,
        )
        state = {
            EnvelopeOutcome.PROCESSING: EnvelopeState.SUBMITTED,
            EnvelopeOutcome.ACCEPTED: EnvelopeState.ACCEPTED,
            EnvelopeOutcome.ACCEPTED_WITH_OBJECTIONS: EnvelopeState.ACCEPTED_WITH_OBJECTIONS,
            EnvelopeOutcome.REJECTED: EnvelopeState.REJECTED,
            EnvelopeOutcome.UNKNOWN: EnvelopeState.UNKNOWN,
        }[status.outcome]
        return self._ledger.update_remote_state(
            envelope.id,
            status=state,
            remote_code=status.status,
            remote_message=(
                f"{status.outcome.value}: informados={status.reported}, "
                f"aceptados={status.accepted}, rechazados={status.rejected}, "
                f"reparos={status.repairs}"
            ),
        )

    def _required_envelope(
        self,
        tenant_id: str,
        envelope_id: str,
    ) -> FiscalEnvelopeRecord:
        envelope = self._ledger.envelope_by_id(envelope_id, tenant_id=tenant_id)
        if envelope is None:
            raise FolioLedgerError("El RCOF no existe para el tenant")
        if envelope.kind != "rcof":
            raise FolioLedgerError("El worker RCOF no admite este tipo de sobre")
        return envelope


class InvoiceEnvelopeWorker:
    """Sube y reconcilia EnvioDTE 33/34 por el gateway DTE heredado."""

    def __init__(self, *, ledger: FolioLedger, api: SiiLegacyDteApi) -> None:
        self._ledger = ledger
        self._api = api

    def submit(self, command: SubmitEnvelopeCommand) -> FiscalEnvelopeRecord:
        envelope = self._required_envelope(command.tenant_id, command.envelope_id)
        attempt = self._ledger.begin_submission(envelope.id)
        try:
            receipt = self._api.upload(
                envelope.signed_xml,
                issuer_rut=envelope.taxpayer_rut,
                sender_rut=command.sender_rut,
                filename=command.filename,
            )
        except Exception as exc:
            return self._ledger.complete_submission(
                attempt.id,
                status=AttemptState.UNKNOWN,
                response_message=f"{type(exc).__name__}: {exc}",
            )
        return self._ledger.complete_submission(
            attempt.id,
            status=AttemptState.SUCCEEDED,
            track_id=receipt.track_id,
            response_code=receipt.status,
            response_message="SII recibió EnvioDTE de facturas",
        )

    def reconcile(self, *, tenant_id: str, envelope_id: str) -> FiscalEnvelopeRecord:
        envelope = self._required_envelope(tenant_id, envelope_id)
        if not envelope.track_id:
            raise FolioLedgerError(
                "El EnvioDTE no tiene Track ID; requiere conciliación operativa asistida"
            )
        status = self._api.get_upload_status(
            issuer_rut=envelope.taxpayer_rut,
            track_id=envelope.track_id,
        )
        state = {
            EnvelopeOutcome.PROCESSING: EnvelopeState.SUBMITTED,
            EnvelopeOutcome.ACCEPTED: EnvelopeState.ACCEPTED,
            EnvelopeOutcome.ACCEPTED_WITH_OBJECTIONS: EnvelopeState.ACCEPTED_WITH_OBJECTIONS,
            EnvelopeOutcome.REJECTED: EnvelopeState.REJECTED,
            EnvelopeOutcome.UNKNOWN: EnvelopeState.UNKNOWN,
        }[status.outcome]
        return self._ledger.update_remote_state(
            envelope.id,
            status=state,
            remote_code=status.status,
            remote_message=status.outcome.value,
        )

    def _required_envelope(
        self,
        tenant_id: str,
        envelope_id: str,
    ) -> FiscalEnvelopeRecord:
        envelope = self._ledger.envelope_by_id(envelope_id, tenant_id=tenant_id)
        if envelope is None:
            raise FolioLedgerError("El EnvioDTE no existe para el tenant")
        if envelope.kind != "envio_dte":
            raise FolioLedgerError("El worker de facturas no admite este tipo de sobre")
        return envelope
