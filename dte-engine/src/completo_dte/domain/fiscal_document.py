"""Contrato canónico previo a builders específicos de cada DTE.

Este módulo no genera XML. Modela el significado tributario estable que pueden
producir la consola fiscal, Completo Restaurantes u otros consumidores.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import IntEnum, StrEnum

from .rut import normalize_rut


class FiscalDocumentError(ValueError):
    """El borrador no representa una operación fiscal coherente."""


class DocumentType(IntEnum):
    FACTURA_AFECTA = 33
    FACTURA_EXENTA = 34
    BOLETA_AFECTA = 39
    BOLETA_EXENTA = 41
    GUIA_DESPACHO = 52
    NOTA_DEBITO = 56
    NOTA_CREDITO = 61


class TaxCategory(StrEnum):
    AFFECTED = "affected"
    EXEMPT = "exempt"
    NON_BILLABLE = "non_billable"


class PriceMode(StrEnum):
    GROSS = "gross"
    NET = "net"


class PaymentMethod(IntEnum):
    CASH = 1
    ELECTRONIC = 2
    TRANSFER = 3
    CHECK = 4
    OTHER = 5


class PaymentTerms(IntEnum):
    CASH = 1
    CREDIT = 2
    FREE = 3


class CorrectionCode(IntEnum):
    VOID = 1
    FIX_TEXT = 2
    FIX_AMOUNT = 3


class DispatchReason(IntEnum):
    SALE = 1
    SALE_PENDING = 2
    CONSIGNMENT = 3
    FREE_DELIVERY = 4
    INTERNAL_TRANSFER = 5
    OTHER_NON_SALE = 6
    RETURN = 7
    EXPORT_TRANSFER = 8
    EXPORT_SALE = 9


@dataclass(frozen=True)
class Party:
    rut: str
    legal_name: str
    business_activity: str | None = None
    address: str | None = None
    commune: str | None = None
    city: str | None = None
    email: str | None = None
    phone: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rut", normalize_rut(self.rut))
        _text(self.legal_name, "razón social", 1, 100)
        _optional_text(self.business_activity, "giro", 80)
        _optional_text(self.address, "dirección", 70)
        _optional_text(self.commune, "comuna", 20)
        _optional_text(self.city, "ciudad", 20)
        _optional_text(self.email, "correo", 80)
        _optional_text(self.phone, "teléfono", 20)


@dataclass(frozen=True)
class FiscalLine:
    name: str
    quantity: Decimal
    unit_price: Decimal
    tax_category: TaxCategory
    price_mode: PriceMode
    unit_measure: str | None = None
    description: str | None = None
    discount_percent: Decimal = Decimal(0)
    discount_amount: Decimal = Decimal(0)
    surcharge_percent: Decimal = Decimal(0)
    surcharge_amount: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        _text(self.name, "nombre del ítem", 1, 80)
        _optional_text(self.unit_measure, "unidad de medida", 4)
        _optional_text(self.description, "descripción adicional", 1000)
        decimals = (
            self.quantity,
            self.unit_price,
            self.discount_percent,
            self.discount_amount,
            self.surcharge_percent,
            self.surcharge_amount,
        )
        if any(not value.is_finite() for value in decimals):
            raise FiscalDocumentError("Cantidades y montos deben ser finitos")
        if self.quantity <= 0 or self.unit_price < 0:
            raise FiscalDocumentError("Cantidad debe ser positiva y precio no negativo")
        if any(value < 0 for value in decimals[2:]):
            raise FiscalDocumentError("Descuentos y recargos no pueden ser negativos")
        if self.discount_percent > 100 or self.surcharge_percent > 1000:
            raise FiscalDocumentError(
                "Porcentajes de descuento o recargo fuera de rango"
            )
        if self.discount_percent and self.discount_amount:
            raise FiscalDocumentError("Informe descuento porcentual o monto, no ambos")
        if self.surcharge_percent and self.surcharge_amount:
            raise FiscalDocumentError("Informe recargo porcentual o monto, no ambos")
        if _scale(self.quantity) > 6 or _scale(self.unit_price) > 6:
            raise FiscalDocumentError("Cantidad y precio admiten hasta 6 decimales")
        if _scale(self.discount_percent) > 2 or _scale(self.surcharge_percent) > 2:
            raise FiscalDocumentError("Porcentajes admiten hasta 2 decimales")


@dataclass(frozen=True)
class FiscalReference:
    line_number: int
    document_type: str
    folio: str | None = None
    issued_on: date | None = None
    correction_code: CorrectionCode | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.line_number <= 40:
            raise FiscalDocumentError("La referencia debe numerarse entre 1 y 40")
        _text(self.document_type, "tipo de referencia", 1, 3)
        _optional_text(self.folio, "folio de referencia", 18)
        _optional_text(self.reason, "razón de referencia", 90)
        if self.correction_code is not None and self.folio is None:
            raise FiscalDocumentError(
                "Una corrección debe identificar el folio original"
            )


@dataclass(frozen=True)
class FiscalDocumentDraft:
    tenant_id: str
    branch_id: str
    issuer_profile_id: str
    document_type: DocumentType
    issued_on: date
    lines: tuple[FiscalLine, ...]
    receiver: Party | None = None
    payment_method: PaymentMethod | None = None
    payment_terms: PaymentTerms | None = None
    due_on: date | None = None
    dispatch_reason: DispatchReason | None = None
    references: tuple[FiscalReference, ...] = ()
    currency: str = "CLP"

    def __post_init__(self) -> None:
        for value, label in (
            (self.tenant_id, "tenant_id"),
            (self.branch_id, "branch_id"),
            (self.issuer_profile_id, "issuer_profile_id"),
        ):
            _token(value, label)
        if not 1 <= len(self.lines) <= 60:
            raise FiscalDocumentError("Un DTE debe contener entre 1 y 60 detalles")
        if self.currency != "CLP":
            raise FiscalDocumentError("La primera versión sólo admite CLP")
        if len({reference.line_number for reference in self.references}) != len(
            self.references
        ):
            raise FiscalDocumentError(
                "Las referencias no pueden repetir número de línea"
            )
        self._validate_document_family()

    def _validate_document_family(self) -> None:
        if (
            self.document_type
            in {
                DocumentType.FACTURA_AFECTA,
                DocumentType.FACTURA_EXENTA,
                DocumentType.GUIA_DESPACHO,
                DocumentType.NOTA_DEBITO,
                DocumentType.NOTA_CREDITO,
            }
            and self.receiver is None
        ):
            raise FiscalDocumentError("Este documento requiere receptor identificado")
        if self.document_type == DocumentType.BOLETA_EXENTA and any(
            line.tax_category == TaxCategory.AFFECTED for line in self.lines
        ):
            raise FiscalDocumentError("La boleta 41 sólo admite líneas exentas")
        if self.document_type == DocumentType.FACTURA_EXENTA and any(
            line.tax_category == TaxCategory.AFFECTED for line in self.lines
        ):
            raise FiscalDocumentError("La factura 34 sólo admite líneas exentas")
        if self.document_type in {
            DocumentType.BOLETA_AFECTA,
            DocumentType.FACTURA_AFECTA,
        } and not any(line.tax_category == TaxCategory.AFFECTED for line in self.lines):
            raise FiscalDocumentError(
                "El documento afecto requiere al menos una línea afecta"
            )
        if self.document_type in {
            DocumentType.NOTA_DEBITO,
            DocumentType.NOTA_CREDITO,
        }:
            if not self.references or not any(
                reference.correction_code is not None for reference in self.references
            ):
                raise FiscalDocumentError(
                    "Una nota debe indicar documento y tipo de corrección"
                )
        if self.document_type == DocumentType.GUIA_DESPACHO:
            if self.dispatch_reason is None:
                raise FiscalDocumentError("La guía debe indicar el motivo del traslado")
        elif self.dispatch_reason is not None:
            raise FiscalDocumentError("El motivo de traslado sólo aplica a guías")
        if self.payment_terms == PaymentTerms.CREDIT and self.due_on is None:
            raise FiscalDocumentError("Una venta a crédito debe indicar vencimiento")
        if self.due_on is not None and self.due_on < self.issued_on:
            raise FiscalDocumentError(
                "El vencimiento no puede ser anterior a la emisión"
            )


def _text(value: str, label: str, minimum: int, maximum: int) -> None:
    try:
        length = len(value.encode("iso-8859-1"))
    except UnicodeEncodeError as exc:
        raise FiscalDocumentError(
            f"{label.capitalize()} contiene caracteres no admitidos"
        ) from exc
    if not minimum <= length <= maximum:
        raise FiscalDocumentError(
            f"{label.capitalize()} debe ocupar entre {minimum} y {maximum} bytes"
        )


def _optional_text(value: str | None, label: str, maximum: int) -> None:
    if value is not None:
        _text(value, label, 1, maximum)


def _token(value: str, label: str) -> None:
    if not value or len(value) > 200 or any(character.isspace() for character in value):
        raise FiscalDocumentError(f"{label} debe ser un identificador no vacío")


def _scale(value: Decimal) -> int:
    return max(0, -value.as_tuple().exponent)
