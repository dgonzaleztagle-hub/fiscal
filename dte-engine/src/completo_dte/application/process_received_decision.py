"""Aceptación/reclamo durable con transporte reemplazable y seguro ante timeouts."""

from dataclasses import dataclass
import hashlib
import json
from typing import Protocol

from completo_dte.domain import ReceivedDecision
from completo_dte.infrastructure import (
    FolioLedger,
    ReceivedDecisionRecord,
    ReceivedDecisionState,
)


class AmbiguousDecisionTransportError(RuntimeError):
    """El servicio pudo recibir la decisión, pero no entregó resultado confiable."""


@dataclass(frozen=True)
class DecisionRemoteResult:
    confirmed: bool
    code: str
    message: str


class ReceivedDecisionGateway(Protocol):
    def submit(self, payload: dict[str, object]) -> DecisionRemoteResult: ...

    def query(self, payload: dict[str, object]) -> DecisionRemoteResult: ...


class ReceivedDecisionService:
    def __init__(self, *, ledger: FolioLedger, gateway: ReceivedDecisionGateway) -> None:
        self._ledger = ledger
        self._gateway = gateway

    def prepare(
        self,
        *,
        tenant_id: str,
        received_document_id: str,
        intent: ReceivedDecision,
    ) -> ReceivedDecisionRecord:
        return self._ledger.prepare_received_decision(
            tenant_id=tenant_id,
            received_document_id=received_document_id,
            decision=intent.decision.value,
            reason=intent.reason,
        )

    def submit(self, decision: ReceivedDecisionRecord) -> ReceivedDecisionRecord:
        received = self._ledger.received_document_by_id(
            decision.received_document_id, tenant_id=decision.tenant_id
        )
        if received is None:
            raise ValueError("El documento recibido desapareció del ledger")
        payload = _payload(decision, received)
        request_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        _submitting, attempt = self._ledger.begin_received_decision_attempt(
            decision.id,
            tenant_id=decision.tenant_id,
            request_sha256=request_hash,
        )
        try:
            result = self._gateway.submit(payload)
        except AmbiguousDecisionTransportError as exc:
            return self._ledger.complete_received_decision_attempt(
                attempt.id,
                state=ReceivedDecisionState.UNKNOWN,
                remote_code=None,
                remote_message=str(exc),
            )
        return self._ledger.complete_received_decision_attempt(
            attempt.id,
            state=(
                ReceivedDecisionState.CONFIRMED
                if result.confirmed
                else ReceivedDecisionState.REJECTED
            ),
            remote_code=result.code,
            remote_message=result.message,
        )

    def reconcile(self, decision: ReceivedDecisionRecord) -> ReceivedDecisionRecord:
        if decision.status is not ReceivedDecisionState.UNKNOWN:
            raise ValueError("Sólo se consulta una decisión de resultado desconocido")
        received = self._ledger.received_document_by_id(
            decision.received_document_id, tenant_id=decision.tenant_id
        )
        if received is None:
            raise ValueError("El documento recibido desapareció del ledger")
        result = self._gateway.query(_payload(decision, received))
        return self._ledger.reconcile_received_decision(
            decision.id,
            tenant_id=decision.tenant_id,
            state=(
                ReceivedDecisionState.CONFIRMED
                if result.confirmed
                else ReceivedDecisionState.REJECTED
            ),
            remote_code=result.code,
            remote_message=result.message,
        )


def _payload(decision, received) -> dict[str, object]:
    codes = {
        "accept_content": "ACD",
        "ack_receipt": "ERM",
        "claim_content": "RCD",
        "claim_partial_delivery": "RFP",
        "claim_total_delivery": "RFT",
    }
    return {
        "receiver_rut": received.receiver_rut,
        "issuer_rut": received.issuer_rut,
        "document_type": received.document_type,
        "folio": received.folio,
        "action_code": codes[decision.decision],
        "reason": decision.reason,
    }
