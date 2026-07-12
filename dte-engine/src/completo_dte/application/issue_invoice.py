"""Orquestación idempotente de facturas 33/34 firmadas."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json

from completo_dte.domain import (
    FiscalDocumentDraft,
    Invoice,
    InvoiceDteBuilder,
    Issuer,
    SigningCredential,
    SignedDte,
    TedBuilder,
    TrustedCafAuthorization,
    XmlSigner,
)
from completo_dte.infrastructure import FiscalDocumentRecord, FolioLedger


@dataclass(frozen=True)
class IssueInvoiceCommand:
    idempotency_key: str
    issuer: Issuer
    draft: FiscalDocumentDraft


class IssueInvoiceService:
    def __init__(
        self,
        *,
        ledger: FolioLedger,
        resolve_caf: Callable[[str], TrustedCafAuthorization],
        resolve_credential: Callable[[str, str], SigningCredential],
        validate_signed_dte: Callable[[SignedDte], None],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._ledger = ledger
        self._resolve_caf = resolve_caf
        self._resolve_credential = resolve_credential
        self._validate_signed_dte = validate_signed_dte
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def issue(self, command: IssueInvoiceCommand) -> FiscalDocumentRecord:
        draft = command.draft
        lease = self._ledger.reserve(
            tenant_id=draft.tenant_id,
            taxpayer_rut=command.issuer.rut,
            document_type=int(draft.document_type),
            idempotency_key=command.idempotency_key,
            request_sha256=invoice_command_sha256(command),
        )
        existing = self._ledger.document_by_lease(lease.id)
        if existing is not None:
            return existing

        caf = self._resolve_caf(lease.caf_range_id)
        if (
            caf.data.issuer_rut != lease.taxpayer_rut
            or caf.data.document_type != lease.document_type
            or not caf.data.folio_from <= lease.folio <= caf.data.folio_to
        ):
            raise ValueError("El CAF resuelto no corresponde a la reserva de factura")

        invoice = Invoice.from_draft(draft, issuer=command.issuer, folio=lease.folio)
        instant = self._clock()
        ted = TedBuilder().build(invoice, caf, generated_at=instant)
        unsigned = InvoiceDteBuilder().build(invoice, ted, signed_at=instant)
        credential = self._resolve_credential(draft.tenant_id, command.issuer.rut)
        signer = XmlSigner()
        signed = signer.sign(unsigned, credential)
        if not signer.verify_with_certificate(signed, credential.certificate):
            raise ValueError(
                "La firma XMLDSig no verificó contra la credencial esperada"
            )
        self._validate_signed_dte(signed)
        return self._ledger.persist_signed_document(
            lease.id,
            document_id=signed.document_id,
            signed_xml=signed.xml,
        )


def invoice_command_sha256(command: IssueInvoiceCommand) -> str:
    draft = command.draft
    receiver = draft.receiver
    payload = {
        "tenant_id": draft.tenant_id,
        "branch_id": draft.branch_id,
        "issuer_profile_id": draft.issuer_profile_id,
        "document_type": int(draft.document_type),
        "issued_on": draft.issued_on.isoformat(),
        "issuer": command.issuer.__dict__,
        "receiver": receiver.__dict__ if receiver is not None else None,
        "payment_terms": int(draft.payment_terms) if draft.payment_terms else None,
        "due_on": draft.due_on.isoformat() if draft.due_on else None,
        "currency": draft.currency,
        "lines": [
            {
                "name": line.name,
                "quantity": _decimal_text(line.quantity),
                "unit_price": _decimal_text(line.unit_price),
                "tax_category": line.tax_category.value,
                "price_mode": line.price_mode.value,
                "unit_measure": line.unit_measure,
                "description": line.description,
                "discount_percent": _decimal_text(line.discount_percent),
                "discount_amount": _decimal_text(line.discount_amount),
                "surcharge_percent": _decimal_text(line.surcharge_percent),
                "surcharge_amount": _decimal_text(line.surcharge_amount),
            }
            for line in draft.lines
        ],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    normalized = text.rstrip("0").rstrip(".") if "." in text else text
    return normalized or "0"
