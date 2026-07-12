"""Codecs puros entre filas SQLite y registros fiscales."""

import sqlite3
from datetime import datetime, timezone

from lxml import etree

from .records import (
    AttemptState,
    DeliveryState,
    EnvelopeState,
    FiscalDeliveryRecord,
    FiscalDocumentRecord,
    FiscalEnvelopeRecord,
    FolioLease,
    FolioLedgerError,
    LeaseState,
    ReceivedClassificationRecord,
    ReceivedDecisionAttemptRecord,
    ReceivedDecisionRecord,
    ReceivedDecisionState,
    ReceivedFiscalDocumentRecord,
    ReceivedLineAllocationRecord,
    ReceivedLineRecord,
    ReceivedSiiObservationRecord,
    SubmissionAttemptRecord,
)


def _lease(row: sqlite3.Row) -> FolioLease:
    return FolioLease(
        id=row["id"],
        tenant_id=row["tenant_id"],
        taxpayer_rut=row["taxpayer_rut"],
        document_type=row["document_type"],
        folio=row["folio"],
        caf_range_id=row["caf_range_id"],
        idempotency_key=row["idempotency_key"],
        request_sha256=row["request_sha256"],
        status=LeaseState(row["status"]),
        document_id=row["document_id"],
        void_reason=row["void_reason"],
    )


def _document(row: sqlite3.Row) -> FiscalDocumentRecord:
    return FiscalDocumentRecord(
        id=row["id"],
        lease_id=row["lease_id"],
        tenant_id=row["tenant_id"],
        taxpayer_rut=row["taxpayer_rut"],
        document_type=row["document_type"],
        folio=row["folio"],
        document_id=row["document_id"],
        xml_sha256=row["xml_sha256"],
        signed_xml=bytes(row["signed_xml"]),
        created_at=row["created_at"],
        public_id=row["public_id"],
    )


def _envelope(row: sqlite3.Row) -> FiscalEnvelopeRecord:
    return FiscalEnvelopeRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        taxpayer_rut=row["taxpayer_rut"],
        kind=row["kind"],
        document_id=row["document_id"],
        xml_sha256=row["xml_sha256"],
        signed_xml=bytes(row["signed_xml"]),
        status=EnvelopeState(row["status"]),
        track_id=row["track_id"],
        remote_code=row["remote_code"],
        remote_message=row["remote_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _attempt(row: sqlite3.Row) -> SubmissionAttemptRecord:
    return SubmissionAttemptRecord(
        id=row["id"],
        envelope_id=row["envelope_id"],
        attempt_number=row["attempt_number"],
        status=AttemptState(row["status"]),
        request_sha256=row["request_sha256"],
        track_id=row["track_id"],
        response_code=row["response_code"],
        response_message=row["response_message"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


def _delivery(row: sqlite3.Row) -> FiscalDeliveryRecord:
    return FiscalDeliveryRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        document_record_id=row["document_record_id"],
        recipient_email=row["recipient_email"],
        kind=row["kind"],
        exchange_xml_sha256=row["exchange_xml_sha256"],
        exchange_xml=bytes(row["exchange_xml"]),
        pdf_sha256=row["pdf_sha256"],
        pdf=bytes(row["pdf"]),
        status=DeliveryState(row["status"]),
        attempt_count=row["attempt_count"],
        provider_id=row["provider_id"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _received_document(row: sqlite3.Row) -> ReceivedFiscalDocumentRecord:
    return ReceivedFiscalDocumentRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        receiver_rut=row["receiver_rut"],
        issuer_rut=row["issuer_rut"],
        issuer_name=row["issuer_name"],
        document_type=row["document_type"],
        folio=row["folio"],
        issued_on=row["issued_on"],
        total=row["total"],
        document_id=row["document_id"],
        xml_sha256=row["xml_sha256"],
        signed_xml=bytes(row["signed_xml"]),
        source=row["source"],
        status=row["status"],
        sii_received_at=row["sii_received_at"],
        received_at=row["received_at"],
    )


def _received_decision(row: sqlite3.Row) -> ReceivedDecisionRecord:
    return ReceivedDecisionRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        received_document_id=row["received_document_id"],
        decision=row["decision"],
        reason=row["reason"],
        status=ReceivedDecisionState(row["status"]),
        remote_code=row["remote_code"],
        remote_message=row["remote_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _received_decision_attempt(row: sqlite3.Row) -> ReceivedDecisionAttemptRecord:
    return ReceivedDecisionAttemptRecord(
        id=row["id"],
        decision_id=row["decision_id"],
        attempt_number=row["attempt_number"],
        status=AttemptState(row["status"]),
        request_sha256=row["request_sha256"],
        remote_code=row["remote_code"],
        remote_message=row["remote_message"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


def _received_classification(row: sqlite3.Row) -> ReceivedClassificationRecord:
    return ReceivedClassificationRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        received_document_id=row["received_document_id"],
        version=row["version"],
        provider_id=row["provider_id"],
        destination=row["destination"],
        category_code=row["category_code"],
        notes=row["notes"],
        classified_by=row["classified_by"],
        created_at=row["created_at"],
    )


def _sii_observation(row: sqlite3.Row) -> ReceivedSiiObservationRecord:
    return ReceivedSiiObservationRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        received_document_id=row["received_document_id"],
        sii_received_at=row["sii_received_at"],
        observed_at=row["observed_at"],
    )


def _received_line(row: sqlite3.Row) -> ReceivedLineRecord:
    return ReceivedLineRecord(
        received_document_id=row["received_document_id"],
        line_number=row["line_number"],
        name=row["name"],
        quantity=row["quantity"],
        amount=row["amount"],
    )


def _line_allocation(row: sqlite3.Row) -> ReceivedLineAllocationRecord:
    return ReceivedLineAllocationRecord(
        classification_id=row["classification_id"],
        line_number=row["line_number"],
        destination=row["destination"],
        control_plane_ref=row["control_plane_ref"],
    )


def _required_token(value: str, label: str) -> None:
    if not value or not value.strip() or len(value) > 200:
        raise FolioLedgerError(f"{label} debe contener entre 1 y 200 caracteres")


def _xml_total(payload: bytes) -> int:
    try:
        root = etree.fromstring(
            payload,
            etree.XMLParser(resolve_entities=False, no_network=True),
        )
        values = root.xpath("//*[local-name()='MntTotal']/text()")
        if len(values) != 1:
            raise ValueError
        total = int(str(values[0]))
        if total < 0:
            raise ValueError
        return total
    except (etree.XMLSyntaxError, TypeError, ValueError) as exc:
        raise FolioLedgerError("El XML no contiene un MntTotal válido") from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")
