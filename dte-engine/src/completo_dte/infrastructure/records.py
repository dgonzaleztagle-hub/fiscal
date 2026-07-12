"""Estados y registros inmutables persistidos por la infraestructura fiscal."""

from dataclasses import dataclass
from enum import StrEnum


class FolioLedgerError(RuntimeError):
    """No se pudo mantener una invariante del ledger de folios."""


class CafRangeExhausted(FolioLedgerError):
    """No quedan folios disponibles para el contribuyente y tipo solicitados."""


class LeaseState(StrEnum):
    RESERVED = "reserved"
    CONSUMED = "consumed"
    VOIDED = "voided"


class EnvelopeState(StrEnum):
    PREPARED = "prepared"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    ACCEPTED_WITH_OBJECTIONS = "accepted_with_objections"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class AttemptState(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class DeliveryState(StrEnum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ReceivedDecisionState(StrEnum):
    PREPARED = "prepared"
    SUBMITTING = "submitting"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FolioLease:
    id: str
    tenant_id: str
    taxpayer_rut: str
    document_type: int
    folio: int
    caf_range_id: str
    idempotency_key: str
    request_sha256: str
    status: LeaseState
    document_id: str | None
    void_reason: str | None


@dataclass(frozen=True)
class FiscalDocumentRecord:
    id: str
    lease_id: str
    tenant_id: str
    taxpayer_rut: str
    document_type: int
    folio: int
    document_id: str
    xml_sha256: str
    signed_xml: bytes
    created_at: str
    public_id: str


@dataclass(frozen=True)
class FiscalEnvelopeRecord:
    id: str
    tenant_id: str
    taxpayer_rut: str
    kind: str
    document_id: str
    xml_sha256: str
    signed_xml: bytes
    status: EnvelopeState
    track_id: str | None
    remote_code: str | None
    remote_message: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class SubmissionAttemptRecord:
    id: str
    envelope_id: str
    attempt_number: int
    status: AttemptState
    request_sha256: str
    track_id: str | None
    response_code: str | None
    response_message: str | None
    started_at: str
    completed_at: str | None


@dataclass(frozen=True)
class FiscalDeliveryRecord:
    id: str
    tenant_id: str
    document_record_id: str
    recipient_email: str
    kind: str
    exchange_xml_sha256: str
    exchange_xml: bytes
    pdf_sha256: str
    pdf: bytes
    status: DeliveryState
    attempt_count: int
    provider_id: str | None
    error_message: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ReceivedFiscalDocumentRecord:
    id: str
    tenant_id: str
    receiver_rut: str
    issuer_rut: str
    issuer_name: str
    document_type: int
    folio: int
    issued_on: str
    total: int
    document_id: str
    xml_sha256: str
    signed_xml: bytes
    source: str
    status: str
    sii_received_at: str | None
    received_at: str


@dataclass(frozen=True)
class ReceivedDecisionRecord:
    id: str
    tenant_id: str
    received_document_id: str
    decision: str
    reason: str | None
    status: ReceivedDecisionState
    remote_code: str | None
    remote_message: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ReceivedDecisionAttemptRecord:
    id: str
    decision_id: str
    attempt_number: int
    status: AttemptState
    request_sha256: str
    remote_code: str | None
    remote_message: str | None
    started_at: str
    completed_at: str | None


@dataclass(frozen=True)
class ReceivedClassificationRecord:
    id: str
    tenant_id: str
    received_document_id: str
    version: int
    provider_id: str | None
    destination: str
    category_code: str | None
    notes: str | None
    classified_by: str
    created_at: str


@dataclass(frozen=True)
class ReceivedSiiObservationRecord:
    id: str
    tenant_id: str
    received_document_id: str
    sii_received_at: str
    observed_at: str


@dataclass(frozen=True)
class ReceivedLineRecord:
    received_document_id: str
    line_number: int
    name: str
    quantity: str | None
    amount: int


@dataclass(frozen=True)
class ReceivedLineAllocationRecord:
    classification_id: str
    line_number: int
    destination: str
    control_plane_ref: str | None
