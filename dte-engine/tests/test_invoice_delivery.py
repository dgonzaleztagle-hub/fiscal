from datetime import date, datetime, timezone
from dataclasses import replace

import pytest

from completo_dte.application import (
    InvoiceDeliveryService,
    InvoiceDeliveryWorker,
    IssueInvoiceService,
)
from completo_dte.domain import EnvelopeAuthorization
from completo_dte.infrastructure import DeliveryState, FolioLedgerError
from completo_dte.presentation import ReceiptConfig
from test_issue_invoice import setup_invoice


class FakeGateway:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def send(self, **payload):
        self.calls.append(payload)
        if self.error:
            raise self.error
        return "mail-provider-123"


def queued_delivery(tmp_path):
    ledger, caf, caf_id, credential, command = setup_invoice(tmp_path)
    receiver = replace(command.draft.receiver, email="facturas@example.test")
    command = replace(command, draft=replace(command.draft, receiver=receiver))
    record = IssueInvoiceService(
        ledger=ledger,
        resolve_caf=lambda requested: caf if requested == caf_id else None,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc),
    ).issue(command)
    delivery = InvoiceDeliveryService(
        ledger=ledger,
        credential=credential,
        authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
        sender_rut="12345678-5",
        receipt_config=ReceiptConfig(
            verification_url="https://documentos.completo.cl",
            resolution_number=80,
            resolution_year=2014,
        ),
        clock=lambda: datetime(2026, 7, 10, 16, tzinfo=timezone.utc),
    ).queue(record)
    return ledger, delivery


def test_delivery_outbox_sends_exact_xml_and_pdf_once(tmp_path) -> None:
    ledger, delivery = queued_delivery(tmp_path)
    gateway = FakeGateway()
    worker = InvoiceDeliveryWorker(ledger=ledger, gateway=gateway)

    sent = worker.deliver(tenant_id="tenant-a", delivery_id=delivery.id)

    assert sent.status is DeliveryState.SENT
    assert sent.provider_id == "mail-provider-123"
    assert len(gateway.calls) == 1
    attachments = gateway.calls[0]["attachments"]
    assert attachments[0].content == delivery.exchange_xml
    assert attachments[1].content == delivery.pdf
    with pytest.raises(FolioLedgerError, match="no debe repetirse"):
        worker.deliver(tenant_id="tenant-a", delivery_id=delivery.id)


def test_delivery_timeout_is_unknown_and_not_retried_blindly(tmp_path) -> None:
    ledger, delivery = queued_delivery(tmp_path)
    gateway = FakeGateway(TimeoutError("respuesta perdida"))
    worker = InvoiceDeliveryWorker(ledger=ledger, gateway=gateway)

    unknown = worker.deliver(tenant_id="tenant-a", delivery_id=delivery.id)

    assert unknown.status is DeliveryState.UNKNOWN
    with pytest.raises(FolioLedgerError, match="conciliarse"):
        worker.deliver(tenant_id="tenant-a", delivery_id=delivery.id)
    assert len(gateway.calls) == 1
