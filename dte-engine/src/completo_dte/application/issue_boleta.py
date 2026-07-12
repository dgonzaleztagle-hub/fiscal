"""Orquestación idempotente de boletas 39/41 firmadas."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json

from completo_dte.domain import (
    BoletaAfecta,
    BoletaExenta,
    BoletaLine,
    DteBuilder,
    Issuer,
    SigningCredential,
    SignedDte,
    TedBuilder,
    TrustedCafAuthorization,
    XmlSigner,
)
from completo_dte.infrastructure import FiscalDocumentRecord, FolioLedger


@dataclass(frozen=True)
class IssueBoletaCommand:
    tenant_id: str
    idempotency_key: str
    issuer: Issuer
    issued_on: date
    lines: tuple[BoletaLine, ...]
    receiver_rut: str = "66666666-6"
    receiver_name: str = "SIN INFORMACION"
    reference_code: str | None = None
    reference_reason: str | None = None
    document_type: int = 39


class IssueBoletaService:
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

    def issue(self, command: IssueBoletaCommand) -> FiscalDocumentRecord:
        lease = self._ledger.reserve(
            tenant_id=command.tenant_id,
            taxpayer_rut=command.issuer.rut,
            document_type=command.document_type,
            idempotency_key=command.idempotency_key,
            request_sha256=command_sha256(command),
        )
        existing = self._ledger.document_by_lease(lease.id)
        if existing is not None:
            return existing

        caf = self._resolve_caf(lease.caf_range_id)
        if caf.data.issuer_rut != lease.taxpayer_rut:
            raise ValueError("El CAF resuelto no pertenece al RUT de la reserva")
        if caf.data.document_type != lease.document_type:
            raise ValueError("El CAF resuelto no corresponde al tipo de la reserva")
        if not caf.data.folio_from <= lease.folio <= caf.data.folio_to:
            raise ValueError("El CAF resuelto no cubre el folio reservado")

        if command.document_type == 39:
            boleta_type = BoletaAfecta
        elif command.document_type == 41:
            boleta_type = BoletaExenta
        else:
            raise ValueError("IssueBoletaService sólo admite tipos 39 y 41")
        boleta = boleta_type(
            issuer=command.issuer,
            folio=lease.folio,
            issued_on=command.issued_on,
            lines=command.lines,
            receiver_rut=command.receiver_rut,
            receiver_name=command.receiver_name,
            reference_code=command.reference_code,
            reference_reason=command.reference_reason,
        )
        instant = self._clock()
        ted = TedBuilder().build(boleta, caf, generated_at=instant)
        unsigned = DteBuilder().build(boleta, ted, signed_at=instant)
        credential = self._resolve_credential(command.tenant_id, command.issuer.rut)
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


def command_sha256(command: IssueBoletaCommand) -> str:
    """Huella canónica del significado tributario de una solicitud."""
    payload = {
        "tenant_id": command.tenant_id,
        "issuer": {
            "rut": command.issuer.rut,
            "legal_name": command.issuer.legal_name,
            "business_activity": command.issuer.business_activity,
            "activity_code": command.issuer.activity_code,
            "address": command.issuer.address,
            "commune": command.issuer.commune,
        },
        "issued_on": command.issued_on.isoformat(),
        "lines": [
            {
                "name": line.name,
                "quantity": _decimal_text(line.quantity),
                "unit_price_gross": _decimal_text(line.unit_price_gross),
                "discount_gross": _decimal_text(line.discount_gross),
                "is_exempt": line.is_exempt,
                "unit_measure": line.unit_measure,
            }
            for line in command.lines
        ],
        "receiver_rut": command.receiver_rut,
        "receiver_name": command.receiver_name,
        "reference_code": command.reference_code,
        "reference_reason": command.reference_reason,
        "document_type": command.document_type,
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
