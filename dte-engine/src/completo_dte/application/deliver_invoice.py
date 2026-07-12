"""Outbox durable para entregar factura, XML de intercambio y PDF al receptor."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from lxml import etree

from completo_dte.domain import (
    EnvelopeAuthorization,
    EnvioDteBuilder,
    SigningCredential,
    SignedDte,
)
from completo_dte.infrastructure import (
    DeliveryState,
    FiscalDeliveryRecord,
    FiscalDocumentRecord,
    FolioLedger,
)
from completo_dte.presentation import InvoiceReceiptRenderer, ReceiptConfig


@dataclass(frozen=True)
class MailAttachment:
    filename: str
    media_type: str
    content: bytes


class MailGateway(Protocol):
    def send(
        self,
        *,
        recipient: str,
        subject: str,
        attachments: tuple[MailAttachment, ...],
    ) -> str: ...


class DefinitiveDeliveryError(RuntimeError):
    """El proveedor confirmó que no realizó la entrega."""


class InvoiceDeliveryService:
    def __init__(
        self,
        *,
        ledger: FolioLedger,
        credential: SigningCredential,
        authorization: EnvelopeAuthorization,
        sender_rut: str,
        receipt_config: ReceiptConfig,
        clock: Callable[[], datetime],
    ) -> None:
        self._ledger = ledger
        self._credential = credential
        self._authorization = authorization
        self._sender_rut = sender_rut
        self._receipt_config = receipt_config
        self._clock = clock

    def queue(
        self,
        record: FiscalDocumentRecord,
        *,
        recipient_email: str | None = None,
    ) -> FiscalDeliveryRecord:
        if record.document_type not in {33, 34}:
            raise ValueError("Sólo se pueden entregar facturas tipos 33 y 34")
        root = etree.fromstring(
            record.signed_xml,
            etree.XMLParser(resolve_entities=False, no_network=True),
        )
        receiver_rut = _one(root, "RUTRecep")
        xml_email = _optional(root, "CorreoRecep")
        email = recipient_email or xml_email
        if email is None:
            raise ValueError("La factura no contiene correo de receptor")
        exchange = EnvioDteBuilder().build(
            (SignedDte(xml=record.signed_xml, document_id=record.document_id),),
            issuer_rut=record.taxpayer_rut,
            sender_rut=self._sender_rut,
            receiver_rut=receiver_rut,
            authorization=self._authorization,
            signed_at=self._clock(),
            credential=self._credential,
            set_id=f"Intercambio_{record.document_id}",
        )
        pdf = InvoiceReceiptRenderer().render(record.signed_xml, self._receipt_config)
        return self._ledger.queue_delivery(
            tenant_id=record.tenant_id,
            document_record_id=record.id,
            recipient_email=email,
            exchange_xml=exchange.xml,
            pdf=pdf,
        )


class InvoiceDeliveryWorker:
    def __init__(self, *, ledger: FolioLedger, gateway: MailGateway) -> None:
        self._ledger = ledger
        self._gateway = gateway

    def deliver(self, *, tenant_id: str, delivery_id: str) -> FiscalDeliveryRecord:
        delivery = self._ledger.begin_delivery(delivery_id, tenant_id=tenant_id)
        attachments = (
            MailAttachment(
                "intercambio-dte.xml", "application/xml", delivery.exchange_xml
            ),
            MailAttachment("factura.pdf", "application/pdf", delivery.pdf),
        )
        try:
            provider_id = self._gateway.send(
                recipient=delivery.recipient_email,
                subject="Documento tributario electrónico",
                attachments=attachments,
            )
        except DefinitiveDeliveryError as exc:
            return self._ledger.complete_delivery(
                delivery.id,
                status=DeliveryState.FAILED,
                error_message=str(exc),
            )
        except Exception as exc:
            return self._ledger.complete_delivery(
                delivery.id,
                status=DeliveryState.UNKNOWN,
                error_message=f"{type(exc).__name__}: {exc}",
            )
        return self._ledger.complete_delivery(
            delivery.id,
            status=DeliveryState.SENT,
            provider_id=provider_id,
        )


def _one(root: etree._Element, name: str) -> str:
    values = root.xpath(f"//*[local-name()='{name}']/text()")
    if len(values) != 1 or not str(values[0]).strip():
        raise ValueError(f"La factura no contiene un único {name}")
    return str(values[0]).strip()


def _optional(root: etree._Element, name: str) -> str | None:
    values = root.xpath(f"//*[local-name()='{name}']/text()")
    if len(values) > 1:
        raise ValueError(f"La factura contiene {name} repetido")
    return str(values[0]).strip() if values and str(values[0]).strip() else None
