"""Contratos HTTP versionados de Completo Fiscal.

Este módulo no contiene lógica tributaria ni acceso a infraestructura.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from completo_dte.domain import (
    CorrectionCode,
    DispatchAccount,
    DispatchReason,
    DocumentType,
    PaymentMethod,
    PaymentTerms,
    PriceMode,
    PurchaseDestination,
    RcvPurchaseStatus,
    ReceivedDecisionType,
    TaxCategory,
)


class IssuerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rut: str
    legal_name: str = Field(min_length=1, max_length=100)
    business_activity: str = Field(min_length=1, max_length=80)
    activity_code: int = Field(ge=1, le=999_999)
    address: str | None = Field(default=None, max_length=70)
    commune: str | None = Field(default=None, max_length=20)


class LineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    unit_price_gross: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    discount_gross: Decimal = Field(
        default=Decimal(0),
        ge=0,
        max_digits=18,
        decimal_places=0,
    )
    is_exempt: bool = False
    unit_measure: str | None = Field(default=None, min_length=1, max_length=4)


class ReferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=18)
    reason: str = Field(min_length=1, max_length=90)


class DocumentResponse(BaseModel):
    id: str
    document_id: str
    document_type: int
    folio: int
    taxpayer_rut: str
    status: str
    xml_sha256: str
    created_at: str
    xml_url: str
    public_url: str
    counterparty_name: str
    issued_on: str
    total: int


class PartyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rut: str
    legal_name: str = Field(min_length=1, max_length=100)
    business_activity: str | None = Field(default=None, max_length=80)
    address: str | None = Field(default=None, max_length=70)
    commune: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=20)


class FiscalLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    tax_category: TaxCategory
    price_mode: PriceMode
    unit_measure: str | None = Field(default=None, min_length=1, max_length=4)
    description: str | None = Field(default=None, max_length=1000)
    discount_percent: Decimal = Field(default=Decimal(0), ge=0, le=100)
    discount_amount: Decimal = Field(default=Decimal(0), ge=0)
    surcharge_percent: Decimal = Field(default=Decimal(0), ge=0, le=1000)
    surcharge_amount: Decimal = Field(default=Decimal(0), ge=0)


class FiscalReferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_number: int = Field(ge=1, le=40)
    document_type: str = Field(min_length=1, max_length=3)
    folio: str | None = Field(default=None, max_length=18)
    issued_on: date | None = None
    correction_code: CorrectionCode | None = None
    reason: str | None = Field(default=None, max_length=90)


class FiscalDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: str = Field(min_length=1, max_length=200)
    issuer_profile_id: str = Field(min_length=1, max_length=200)
    document_type: DocumentType
    issued_on: date
    lines: tuple[FiscalLineRequest, ...] = Field(min_length=1, max_length=60)
    receiver: PartyRequest | None = None
    payment_method: PaymentMethod | None = None
    payment_terms: PaymentTerms | None = None
    due_on: date | None = None
    dispatch_reason: DispatchReason | None = None
    references: tuple[FiscalReferenceRequest, ...] = Field(default=(), max_length=40)
    currency: str = Field(default="CLP", min_length=3, max_length=3)


class IssueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType = DocumentType.BOLETA_AFECTA
    issued_on: date
    issuer: IssuerRequest
    lines: tuple[LineRequest | FiscalLineRequest, ...] = Field(
        min_length=1,
        max_length=60,
    )
    branch_id: str = Field(default="main", min_length=1, max_length=200)
    issuer_profile_id: str = Field(default="default", min_length=1, max_length=200)
    receiver: PartyRequest | None = None
    receiver_rut: str = "66666666-6"
    receiver_name: str = Field(default="SIN INFORMACION", min_length=1, max_length=40)
    payment_terms: PaymentTerms | None = None
    due_on: date | None = None
    dispatch_reason: DispatchReason | None = None
    dispatch_account: DispatchAccount | None = None
    transport: "DispatchTransportRequest | None" = None
    reference: ReferenceRequest | None = None


class DispatchTransportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_plate: str | None = Field(default=None, max_length=8)
    carrier_rut: str | None = None
    driver_rut: str | None = None
    driver_name: str | None = Field(default=None, max_length=30)
    destination_address: str | None = Field(default=None, max_length=70)
    destination_commune: str | None = Field(default=None, max_length=20)
    destination_city: str | None = Field(default=None, max_length=20)


class DraftValidationResponse(BaseModel):
    valid: bool
    document_type: int
    document_name: str
    line_count: int
    receiver_required: bool
    builder_status: str


class EventResponse(BaseModel):
    sequence: int
    event_type: str
    occurred_at: str
    metadata: dict[str, object]


class EnvelopeResponse(BaseModel):
    id: str
    kind: str
    document_id: str
    taxpayer_rut: str
    status: str
    track_id: str | None
    xml_sha256: str
    created_at: str
    updated_at: str


class OperationalAlertResponse(BaseModel):
    code: str
    severity: str
    message: str
    resource_id: str | None


class DeliveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_email: str | None = Field(default=None, max_length=254)


class DeliveryResponse(BaseModel):
    id: str
    document_record_id: str
    recipient_email: str
    status: str
    attempt_count: int
    exchange_xml_sha256: str
    pdf_sha256: str
    provider_id: str | None
    error_message: str | None
    created_at: str
    updated_at: str


class CorrectionIssueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    issued_on: date
    issuer: IssuerRequest
    lines: tuple[FiscalLineRequest, ...] = Field(min_length=1, max_length=60)
    reason: str = Field(min_length=1, max_length=90)


class AnnulmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issued_on: date


class TextCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issued_on: date
    business_activity: str = Field(min_length=1, max_length=40)
    address: str = Field(min_length=1, max_length=70)
    commune: str = Field(min_length=1, max_length=20)


class ReceivedDocumentResponse(BaseModel):
    id: str
    issuer_rut: str
    issuer_name: str
    document_type: int
    folio: int
    issued_on: str
    total: int
    status: str
    source: str
    xml_sha256: str
    sii_received_at: str | None
    received_at: str


class ReceivedDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ReceivedDecisionType
    reason: str | None = Field(default=None, max_length=200)


class ReceivedDecisionResponse(BaseModel):
    id: str
    received_document_id: str
    decision: str
    reason: str | None
    status: str
    remote_code: str | None
    remote_message: str | None
    created_at: str
    updated_at: str


class ReceivedClassificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str | None = Field(default=None, max_length=200)
    destination: str
    category_code: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=1000)


class ReceivedClassificationResponse(BaseModel):
    id: str
    received_document_id: str
    version: int
    provider_id: str | None
    destination: str
    category_code: str | None
    notes: str | None
    classified_by: str
    created_at: str


class RcvEntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issuer_rut: str
    document_type: DocumentType
    folio: int = Field(gt=0)
    issued_on: date
    exempt_amount: int = Field(ge=0)
    net_amount: int = Field(ge=0)
    vat_amount: int = Field(ge=0)
    total_amount: int = Field(ge=0)
    status: RcvPurchaseStatus


class RcvImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    source: str
    entries: tuple[RcvEntryRequest, ...] = Field(max_length=10000)


class RcvSnapshotResponse(BaseModel):
    id: str
    period: str
    version: int
    source: str
    payload_sha256: str
    imported_at: str


class RcvDifferenceResponse(BaseModel):
    kind: str
    issuer_rut: str
    document_type: int
    folio: int
    xml_total: int | None
    rcv_total: int | None


class PurchaseLineAllocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_number: int = Field(gt=0)
    destination: PurchaseDestination
    control_plane_ref: str | None = Field(default=None, max_length=200)


class PurchaseAllocationsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allocations: tuple[PurchaseLineAllocationRequest, ...] = Field(
        min_length=1, max_length=60
    )


class CertificationDryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: str = Field(default="accepted", max_length=40)


class CertificationDryRunResponse(BaseModel):
    synthetic: bool
    document_count: int
    envelope_document_id: str
    rcof_document_id: str
    scenario: str
    final_state: str
    evidence_sha256: str
    timeline: list[dict[str, str]]


class CertificationReadinessResponse(BaseModel):
    ready_to_download_caf: bool
    completed: int
    total: int
    gates: list[dict[str, object]]
