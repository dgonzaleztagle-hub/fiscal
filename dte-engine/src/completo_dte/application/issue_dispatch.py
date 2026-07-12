"""Orquestación idempotente de guías de despacho 52 firmadas."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json

from completo_dte.domain import (
    DispatchAccount,
    DispatchDocument,
    DispatchDteBuilder,
    DispatchTransport,
    FiscalDocumentDraft,
    Issuer,
    SigningCredential,
    SignedDte,
    TedBuilder,
    TrustedCafAuthorization,
    XmlSigner,
)
from completo_dte.infrastructure import FiscalDocumentRecord, FolioLedger
from .issue_invoice import _decimal_text


@dataclass(frozen=True)
class IssueDispatchCommand:
    idempotency_key: str
    issuer: Issuer
    draft: FiscalDocumentDraft
    transport: DispatchTransport
    dispatch_account: DispatchAccount | None


class IssueDispatchService:
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

    def issue(self, command: IssueDispatchCommand) -> FiscalDocumentRecord:
        draft = command.draft
        lease = self._ledger.reserve(
            tenant_id=draft.tenant_id,
            taxpayer_rut=command.issuer.rut,
            document_type=52,
            idempotency_key=command.idempotency_key,
            request_sha256=dispatch_command_sha256(command),
        )
        existing = self._ledger.document_by_lease(lease.id)
        if existing is not None:
            return existing
        caf = self._resolve_caf(lease.caf_range_id)
        if (
            caf.data.issuer_rut != lease.taxpayer_rut
            or caf.data.document_type != 52
            or not caf.data.folio_from <= lease.folio <= caf.data.folio_to
        ):
            raise ValueError("El CAF resuelto no corresponde a la reserva de guía")
        guide = DispatchDocument.from_draft(
            draft,
            issuer=command.issuer,
            folio=lease.folio,
            transport=command.transport,
            dispatch_account=command.dispatch_account,
        )
        instant = self._clock()
        ted = TedBuilder().build(guide, caf, generated_at=instant)
        unsigned = DispatchDteBuilder().build(guide, ted, signed_at=instant)
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


def dispatch_command_sha256(command: IssueDispatchCommand) -> str:
    draft = command.draft
    payload = {
        "tenant_id": draft.tenant_id,
        "branch_id": draft.branch_id,
        "issuer_profile_id": draft.issuer_profile_id,
        "issued_on": draft.issued_on.isoformat(),
        "reason": int(draft.dispatch_reason) if draft.dispatch_reason else None,
        "dispatch_account": int(command.dispatch_account)
        if command.dispatch_account
        else None,
        "issuer": command.issuer.__dict__,
        "receiver": draft.receiver.__dict__ if draft.receiver else None,
        "transport": {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in command.transport.__dict__.items()
        },
        "lines": [
            {
                "name": line.name,
                "quantity": _decimal_text(line.quantity),
                "unit_price": _decimal_text(line.unit_price),
                "tax_category": line.tax_category.value,
                "price_mode": line.price_mode.value,
                "unit_measure": line.unit_measure,
                "description": line.description,
            }
            for line in draft.lines
        ],
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
