from dataclasses import dataclass

import pytest

from completo_dte.application import (
    AmbiguousDecisionTransportError,
    DecisionRemoteResult,
    ReceivedDecisionService,
)
from completo_dte.domain import (
    ReceivedDecision,
    ReceivedDecisionError,
    ReceivedDecisionType,
)
from completo_dte.infrastructure import FolioLedger, FolioLedgerError, ReceivedDecisionState
from test_received_ledger import received_document


@dataclass
class FakeGateway:
    submit_result: DecisionRemoteResult | Exception
    query_result: DecisionRemoteResult | None = None
    submitted: dict | None = None

    def submit(self, payload):
        self.submitted = payload
        if isinstance(self.submit_result, Exception):
            raise self.submit_result
        return self.submit_result

    def query(self, payload):
        assert payload == self.submitted
        assert self.query_result is not None
        return self.query_result


def setup_service(tmp_path, gateway):
    ledger = FolioLedger(tmp_path / "decisions.sqlite3")
    ledger.migrate()
    received = ledger.import_received_document(
        tenant_id="tenant-a", document=received_document(), source="upload"
    )
    return ledger, received, ReceivedDecisionService(ledger=ledger, gateway=gateway)


def test_acceptance_is_submitted_once_and_confirmed(tmp_path) -> None:
    gateway = FakeGateway(DecisionRemoteResult(True, "0", "Aceptado"))
    ledger, received, service = setup_service(tmp_path, gateway)
    decision = service.prepare(
        tenant_id="tenant-a",
        received_document_id=received.id,
        intent=ReceivedDecision(ReceivedDecisionType.ACCEPT_CONTENT),
    )
    confirmed = service.submit(decision)

    assert confirmed.status is ReceivedDecisionState.CONFIRMED
    assert gateway.submitted["action_code"] == "ACD"
    with pytest.raises(FolioLedgerError, match="ya fue enviada"):
        service.submit(decision)


def test_timeout_becomes_unknown_and_is_reconciled_without_resubmit(tmp_path) -> None:
    gateway = FakeGateway(
        AmbiguousDecisionTransportError("timeout posterior al envío"),
        DecisionRemoteResult(True, "0", "Reclamo registrado"),
    )
    _ledger, received, service = setup_service(tmp_path, gateway)
    decision = service.prepare(
        tenant_id="tenant-a",
        received_document_id=received.id,
        intent=ReceivedDecision(
            ReceivedDecisionType.CLAIM_CONTENT,
            "El total no corresponde a la compra recibida",
        ),
    )
    unknown = service.submit(decision)
    assert unknown.status is ReceivedDecisionState.UNKNOWN
    assert gateway.submitted["action_code"] == "RCD"

    reconciled = service.reconcile(unknown)
    assert reconciled.status is ReceivedDecisionState.CONFIRMED


def test_conflicting_decisions_and_cross_tenant_access_are_blocked(tmp_path) -> None:
    gateway = FakeGateway(DecisionRemoteResult(True, "0", "Aceptado"))
    ledger, received, service = setup_service(tmp_path, gateway)
    service.prepare(
        tenant_id="tenant-a",
        received_document_id=received.id,
        intent=ReceivedDecision(ReceivedDecisionType.ACCEPT_CONTENT),
    )
    with pytest.raises(FolioLedgerError, match="incompatible"):
        service.prepare(
            tenant_id="tenant-a",
            received_document_id=received.id,
            intent=ReceivedDecision(
                ReceivedDecisionType.CLAIM_TOTAL_DELIVERY,
                "Mercadería no recibida",
            ),
        )
    with pytest.raises(FolioLedgerError, match="no encontrado"):
        ledger.prepare_received_decision(
            tenant_id="tenant-b",
            received_document_id=received.id,
            decision="accept_content",
            reason=None,
        )


def test_reclaim_requires_reason_and_acceptance_forbids_it() -> None:
    with pytest.raises(ReceivedDecisionError, match="requiere una razón"):
        ReceivedDecision(ReceivedDecisionType.CLAIM_PARTIAL_DELIVERY)
    with pytest.raises(ReceivedDecisionError, match="aceptación"):
        ReceivedDecision(ReceivedDecisionType.ACCEPT_CONTENT, "No aplica")


def test_accept_content_and_receipt_can_coexist_but_block_later_claim(tmp_path) -> None:
    gateway = FakeGateway(DecisionRemoteResult(True, "0", "Registrado"))
    ledger, received, service = setup_service(tmp_path, gateway)
    accepted = service.prepare(
        tenant_id="tenant-a",
        received_document_id=received.id,
        intent=ReceivedDecision(ReceivedDecisionType.ACCEPT_CONTENT),
    )
    receipt = service.prepare(
        tenant_id="tenant-a",
        received_document_id=received.id,
        intent=ReceivedDecision(ReceivedDecisionType.ACK_RECEIPT),
    )
    assert accepted.decision == "accept_content"
    assert receipt.decision == "ack_receipt"
    with pytest.raises(FolioLedgerError, match="incompatible"):
        service.prepare(
            tenant_id="tenant-a",
            received_document_id=received.id,
            intent=ReceivedDecision(
                ReceivedDecisionType.CLAIM_CONTENT, "Documento incorrecto"
            ),
        )
