"""Emisión idempotente de notas 56/61 que corrigen montos."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json

from lxml import etree

from completo_dte.domain import (
    CorrectionDocument,
    CorrectionDteBuilder,
    CorrectionCode,
    CorrectionReference,
    DocumentType,
    FiscalLine,
    Issuer,
    Party,
    PriceMode,
    SigningCredential,
    SignedDte,
    TedBuilder,
    TrustedCafAuthorization,
    TaxCategory,
    XmlSigner,
)
from completo_dte.infrastructure import FiscalDocumentRecord, FolioLedger


@dataclass(frozen=True)
class IssueCorrectionCommand:
    tenant_id: str
    idempotency_key: str
    target_record_id: str
    correction: CorrectionDocument


@dataclass(frozen=True)
class AnnulDocumentCommand:
    tenant_id: str
    idempotency_key: str
    target_record_id: str
    issued_on: date


@dataclass(frozen=True)
class CorrectTextCommand:
    tenant_id: str
    idempotency_key: str
    target_record_id: str
    issued_on: date
    business_activity: str
    address: str
    commune: str


class IssueCorrectionService:
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

    def annul(self, command: AnnulDocumentCommand) -> FiscalDocumentRecord:
        target = self._ledger.document_by_id(
            command.target_record_id,
            tenant_id=command.tenant_id,
        )
        if target is None:
            raise ValueError("El documento original no existe para el tenant")
        if target.document_type not in {33, 34, 56}:
            raise ValueError("Sólo se puede anular factura 33/34 o nota de débito 56")
        root = etree.fromstring(
            target.signed_xml,
            etree.XMLParser(resolve_entities=False, no_network=True),
        )
        correction = _annulment_from_xml(root, command.issued_on)
        return self.issue(
            IssueCorrectionCommand(
                tenant_id=command.tenant_id,
                idempotency_key=command.idempotency_key,
                target_record_id=target.id,
                correction=correction,
            )
        )

    def correct_text(self, command: CorrectTextCommand) -> FiscalDocumentRecord:
        target = self._ledger.document_by_id(
            command.target_record_id,
            tenant_id=command.tenant_id,
        )
        if target is None or target.document_type not in {33, 34}:
            raise ValueError("La corrección de texto requiere factura original 33/34")
        root = etree.fromstring(
            target.signed_xml,
            etree.XMLParser(resolve_entities=False, no_network=True),
        )
        base = _annulment_from_xml(root, command.issued_on)
        receiver = replace(
            base.receiver,
            business_activity=command.business_activity,
            address=command.address,
            commune=command.commune,
        )
        if receiver == base.receiver:
            raise ValueError("La corrección de texto no contiene ningún cambio")
        original_type = base.reference.document_type
        correction = replace(
            base,
            receiver=receiver,
            lines=(
                FiscalLine(
                    name="CORRIGE GIRO DIRECCION O COMUNA",
                    quantity=Decimal(1),
                    unit_price=Decimal(0),
                    tax_category=(
                        TaxCategory.EXEMPT
                        if original_type is DocumentType.FACTURA_EXENTA
                        else TaxCategory.AFFECTED
                    ),
                    price_mode=PriceMode.NET,
                ),
            ),
            reference=replace(
                base.reference,
                code=CorrectionCode.FIX_TEXT,
                reason="CORRIGE TEXTO",
            ),
        )
        return self.issue(
            IssueCorrectionCommand(
                tenant_id=command.tenant_id,
                idempotency_key=command.idempotency_key,
                target_record_id=target.id,
                correction=correction,
            )
        )

    def issue(self, command: IssueCorrectionCommand) -> FiscalDocumentRecord:
        note = command.correction
        target = self._ledger.document_by_id(
            command.target_record_id,
            tenant_id=command.tenant_id,
        )
        if target is None:
            raise ValueError("El documento original no existe para el tenant")
        reference = note.reference
        if (
            target.document_type != int(reference.document_type)
            or target.folio != reference.folio
        ):
            raise ValueError("La referencia no coincide con el documento original")
        target_root = etree.fromstring(
            target.signed_xml,
            etree.XMLParser(resolve_entities=False, no_network=True),
        )
        if _one(target_root, "FchEmis") != reference.issued_on.isoformat():
            raise ValueError(
                "La fecha de referencia no coincide con el documento original"
            )
        if _one(target_root, "RUTRecep") != note.receiver.rut:
            raise ValueError(
                "La nota no puede cambiar el RUT receptor del documento original"
            )
        lease = self._ledger.reserve(
            tenant_id=command.tenant_id,
            taxpayer_rut=note.issuer.rut,
            document_type=int(note.document_type),
            idempotency_key=command.idempotency_key,
            request_sha256=correction_command_sha256(command),
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
            raise ValueError("El CAF no corresponde a la reserva de la nota")
        note = replace(note, folio=lease.folio)
        instant = self._clock()
        ted = TedBuilder().build(note, caf, generated_at=instant)
        unsigned = CorrectionDteBuilder().build(note, ted, signed_at=instant)
        credential = self._resolve_credential(command.tenant_id, note.issuer.rut)
        signer = XmlSigner()
        signed = signer.sign(unsigned, credential)
        if not signer.verify_with_certificate(signed, credential.certificate):
            raise ValueError("La firma de la nota no verificó")
        self._validate_signed_dte(signed)
        return self._ledger.persist_signed_document(
            lease.id,
            document_id=signed.document_id,
            signed_xml=signed.xml,
            corrects_record_id=target.id,
            correction_code=int(reference.code),
        )


def correction_command_sha256(command: IssueCorrectionCommand) -> str:
    note = command.correction
    payload = {
        "tenant_id": command.tenant_id,
        "target_record_id": command.target_record_id,
        "document_type": int(note.document_type),
        "issued_on": note.issued_on.isoformat(),
        "reference": {
            "document_type": int(note.reference.document_type),
            "folio": note.reference.folio,
            "issued_on": note.reference.issued_on.isoformat(),
            "code": int(note.reference.code),
            "reason": note.reference.reason,
        },
        "lines": [
            {
                "name": line.name,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "tax_category": line.tax_category.value,
                "price_mode": line.price_mode.value,
            }
            for line in note.lines
        ],
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _one(root: etree._Element, name: str) -> str:
    values = root.xpath(f"//*[local-name()='{name}']/text()")
    if len(values) != 1 or not str(values[0]).strip():
        raise ValueError(f"El documento original no contiene un único {name}")
    return str(values[0]).strip()


def _annulment_from_xml(root: etree._Element, issued_on: date) -> CorrectionDocument:
    original_type = DocumentType(int(_one(root, "TipoDTE")))
    original_date = date.fromisoformat(_one(root, "FchEmis"))
    issuer = Issuer(
        rut=_one(root, "RUTEmisor"),
        legal_name=_one(root, "RznSoc"),
        business_activity=_one(root, "GiroEmis"),
        activity_code=int(_one(root, "Acteco")),
        address=_optional(root, "DirOrigen"),
        commune=_optional(root, "CmnaOrigen"),
    )
    receiver = Party(
        rut=_one(root, "RUTRecep"),
        legal_name=_one(root, "RznSocRecep"),
        business_activity=_one(root, "GiroRecep"),
        address=_one(root, "DirRecep"),
        commune=_one(root, "CmnaRecep"),
        email=_optional(root, "CorreoRecep"),
    )
    details = root.xpath("//*[local-name()='Detalle']")
    lines = tuple(
        FiscalLine(
            name=_child_one(detail, "NmbItem"),
            description=_child_optional(detail, "DscItem"),
            quantity=Decimal(_child_one(detail, "QtyItem")),
            unit_price=Decimal(_child_one(detail, "PrcItem")),
            unit_measure=_child_optional(detail, "UnmdItem"),
            tax_category=(
                TaxCategory.EXEMPT
                if original_type is DocumentType.FACTURA_EXENTA
                or _child_optional(detail, "IndExe") == "1"
                else TaxCategory.AFFECTED
            ),
            price_mode=PriceMode.NET,
            discount_percent=Decimal(_child_optional(detail, "DescuentoPct") or 0),
            discount_amount=Decimal(_child_optional(detail, "DescuentoMonto") or 0),
            surcharge_percent=Decimal(_child_optional(detail, "RecargoPct") or 0),
            surcharge_amount=Decimal(_child_optional(detail, "RecargoMonto") or 0),
        )
        for detail in details
    )
    return CorrectionDocument(
        issuer=issuer,
        receiver=receiver,
        document_type=DocumentType.NOTA_CREDITO,
        folio=1,
        issued_on=issued_on,
        lines=lines,
        reference=CorrectionReference(
            document_type=original_type,
            folio=int(_one(root, "Folio")),
            issued_on=original_date,
            code=CorrectionCode.VOID,
            reason="ANULA DOCUMENTO DE REFERENCIA",
        ),
    )


def _optional(root: etree._Element, name: str) -> str | None:
    values = root.xpath(f"//*[local-name()='{name}']/text()")
    if len(values) > 1:
        raise ValueError(f"El documento contiene {name} repetido")
    return str(values[0]).strip() if values and str(values[0]).strip() else None


def _child_one(root: etree._Element, name: str) -> str:
    value = _child_optional(root, name)
    if value is None:
        raise ValueError(f"El detalle no contiene {name}")
    return value


def _child_optional(root: etree._Element, name: str) -> str | None:
    values = root.xpath(f"./*[local-name()='{name}']/text()")
    if len(values) > 1:
        raise ValueError(f"El detalle contiene {name} repetido")
    return str(values[0]).strip() if values and str(values[0]).strip() else None
