"""Proyecciones HTTP desde registros fiscales inmutables."""

from fastapi import Request
from lxml import etree

from completo_dte.domain import DocumentType
from completo_dte.infrastructure import FiscalDeliveryRecord, FiscalDocumentRecord

from .contracts import (
    DeliveryResponse,
    DocumentResponse,
    RcvSnapshotResponse,
    ReceivedClassificationResponse,
    ReceivedDecisionResponse,
    ReceivedDocumentResponse,
)


def _response(record: FiscalDocumentRecord, request: Request) -> DocumentResponse:
    xml_url = str(request.url_for("get_document_xml", record_id=record.id))
    public_url = str(request.url_for("public_receipt_page", public_id=record.public_id))
    try:
        root = etree.fromstring(
            record.signed_xml,
            etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False),
        )
        counterparty = _xml_optional(root, "RznSocRecep") or "Consumidor final"
        issued_on = _xml_one(root, "FchEmis")
        total = int(_xml_one(root, "MntTotal"))
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise RuntimeError("Documento fiscal persistido no puede proyectarse") from exc
    return DocumentResponse(
        id=record.id,
        document_id=record.document_id,
        document_type=record.document_type,
        folio=record.folio,
        taxpayer_rut=record.taxpayer_rut,
        status="signed",
        xml_sha256=record.xml_sha256,
        created_at=record.created_at,
        xml_url=xml_url,
        public_url=public_url,
        counterparty_name=counterparty,
        issued_on=issued_on,
        total=total,
    )


def _delivery_response(record: FiscalDeliveryRecord) -> DeliveryResponse:
    return DeliveryResponse(
        id=record.id,
        document_record_id=record.document_record_id,
        recipient_email=record.recipient_email,
        status=record.status.value,
        attempt_count=record.attempt_count,
        exchange_xml_sha256=record.exchange_xml_sha256,
        pdf_sha256=record.pdf_sha256,
        provider_id=record.provider_id,
        error_message=record.error_message,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _received_response(record) -> ReceivedDocumentResponse:
    return ReceivedDocumentResponse(
        id=record.id,
        issuer_rut=record.issuer_rut,
        issuer_name=record.issuer_name,
        document_type=record.document_type,
        folio=record.folio,
        issued_on=record.issued_on,
        total=record.total,
        status=record.status,
        source=record.source,
        xml_sha256=record.xml_sha256,
        sii_received_at=record.sii_received_at,
        received_at=record.received_at,
    )


def _received_decision_response(record) -> ReceivedDecisionResponse:
    return ReceivedDecisionResponse(
        id=record.id,
        received_document_id=record.received_document_id,
        decision=record.decision,
        reason=record.reason,
        status=record.status.value,
        remote_code=record.remote_code,
        remote_message=record.remote_message,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _received_classification_response(record) -> ReceivedClassificationResponse:
    return ReceivedClassificationResponse(
        id=record.id,
        received_document_id=record.received_document_id,
        version=record.version,
        provider_id=record.provider_id,
        destination=record.destination,
        category_code=record.category_code,
        notes=record.notes,
        classified_by=record.classified_by,
        created_at=record.created_at,
    )


def _rcv_snapshot_response(record) -> RcvSnapshotResponse:
    return RcvSnapshotResponse(
        id=record.id,
        period=record.period,
        version=record.version,
        source=record.source,
        payload_sha256=record.payload_sha256,
        imported_at=record.imported_at,
    )


def _xml_one(root: etree._Element, name: str) -> str:
    values = root.xpath(f"//*[local-name()='{name}']/text()")
    if len(values) != 1 or not str(values[0]).strip():
        raise ValueError(f"El documento no contiene un único {name}")
    return str(values[0]).strip()


def _xml_optional(root: etree._Element, name: str) -> str | None:
    values = root.xpath(f"//*[local-name()='{name}']/text()")
    if len(values) > 1:
        raise ValueError(f"El documento contiene {name} repetido")
    return str(values[0]).strip() if values and str(values[0]).strip() else None


def _document_name(document_type: DocumentType) -> str:
    return {
        DocumentType.FACTURA_AFECTA: "Factura electrónica",
        DocumentType.FACTURA_EXENTA: "Factura exenta electrónica",
        DocumentType.BOLETA_AFECTA: "Boleta electrónica",
        DocumentType.BOLETA_EXENTA: "Boleta exenta electrónica",
        DocumentType.GUIA_DESPACHO: "Guía de despacho electrónica",
        DocumentType.NOTA_DEBITO: "Nota de débito electrónica",
        DocumentType.NOTA_CREDITO: "Nota de crédito electrónica",
    }[document_type]
