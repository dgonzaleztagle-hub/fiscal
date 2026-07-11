"""Reglas base de notas 56/61 que corrigen montos."""

from dataclasses import dataclass
from datetime import date
from calendar import monthrange
from decimal import Decimal

from .boleta import IVA_RATE, MAX_ISSUE_DATE, Issuer
from .fiscal_document import (
    CorrectionCode,
    DocumentType,
    FiscalLine,
    Party,
    PriceMode,
    TaxCategory,
)
from .invoice import _clp, calculate_line_amounts


class CorrectionError(ValueError):
    """La nota no representa una corrección tributaria coherente."""


@dataclass(frozen=True)
class CorrectionReference:
    document_type: DocumentType
    folio: int
    issued_on: date
    code: CorrectionCode
    reason: str

    def __post_init__(self) -> None:
        if self.document_type not in {
            DocumentType.FACTURA_AFECTA,
            DocumentType.FACTURA_EXENTA,
            DocumentType.NOTA_DEBITO,
            DocumentType.NOTA_CREDITO,
        }:
            raise CorrectionError("El tipo original no admite esta corrección")
        if not 1 <= self.folio <= 9_999_999_999:
            raise CorrectionError("Folio original inválido")
        if not self.reason.strip() or len(self.reason.encode("iso-8859-1")) > 90:
            raise CorrectionError("La razón de referencia debe ocupar entre 1 y 90 bytes")


@dataclass(frozen=True)
class CorrectionDocument:
    issuer: Issuer
    receiver: Party
    document_type: DocumentType
    folio: int
    issued_on: date
    lines: tuple[FiscalLine, ...]
    reference: CorrectionReference

    def __post_init__(self) -> None:
        if self.document_type not in {DocumentType.NOTA_DEBITO, DocumentType.NOTA_CREDITO}:
            raise CorrectionError("Sólo se admiten notas tipos 56 y 61")
        if self.reference.code is CorrectionCode.FIX_TEXT:
            if self.document_type is not DocumentType.NOTA_CREDITO:
                raise CorrectionError("La corrección de texto requiere nota de crédito 61")
            if self.reference.document_type not in {
                DocumentType.FACTURA_AFECTA,
                DocumentType.FACTURA_EXENTA,
            }:
                raise CorrectionError("La corrección de texto debe referenciar factura 33/34")
            if (
                len(self.lines) != 1
                or self.lines[0].quantity != 1
                or self.lines[0].unit_price != 0
            ):
                raise CorrectionError(
                    "La corrección de texto requiere una línea descriptiva sin monto"
                )
        elif self.reference.code is CorrectionCode.FIX_AMOUNT:
            if self.reference.document_type not in {
                DocumentType.FACTURA_AFECTA,
                DocumentType.FACTURA_EXENTA,
            }:
                raise CorrectionError("La corrección de montos debe referenciar factura 33/34")
        elif self.reference.code is CorrectionCode.VOID:
            if self.document_type is not DocumentType.NOTA_CREDITO:
                raise CorrectionError("La anulación se genera mediante nota de crédito 61")
            if self.reference.document_type not in {
                DocumentType.FACTURA_AFECTA,
                DocumentType.FACTURA_EXENTA,
                DocumentType.NOTA_DEBITO,
            }:
                raise CorrectionError("La nota 61 no puede anular ese tipo documental")
        if not 1 <= self.folio <= 9_999_999_999:
            raise CorrectionError("Folio de la nota inválido")
        if not date(2003, 4, 1) <= self.issued_on <= MAX_ISSUE_DATE:
            raise CorrectionError("Fecha de la nota fuera de rango")
        if self.issued_on < self.reference.issued_on:
            raise CorrectionError("La nota no puede ser anterior al documento original")
        if (
            self.reference.code is CorrectionCode.VOID
            and self.issued_on > _end_of_following_month(self.reference.issued_on)
        ):
            raise CorrectionError(
                "La anulación excede el período de emisión o el período siguiente"
            )
        if not 1 <= len(self.lines) <= 60:
            raise CorrectionError("La nota debe contener entre 1 y 60 ítems")
        if any(
            value is None
            for value in (
                self.receiver.business_activity,
                self.receiver.address,
                self.receiver.commune,
            )
        ):
            raise CorrectionError("La nota requiere giro, dirección y comuna del receptor")
        if any(line.tax_category == TaxCategory.NON_BILLABLE for line in self.lines):
            raise CorrectionError("La corrección de montos no admite líneas no facturables")
        if any(
            line.tax_category == TaxCategory.AFFECTED and line.price_mode != PriceMode.NET
            for line in self.lines
        ):
            raise CorrectionError("Las líneas afectas deben informar precio neto")
        if self.reference.document_type == DocumentType.FACTURA_EXENTA and any(
            line.tax_category != TaxCategory.EXEMPT for line in self.lines
        ):
            raise CorrectionError("Una corrección de factura 34 sólo admite montos exentos")
        if self.reference.code is CorrectionCode.FIX_TEXT and self.total != 0:
            raise CorrectionError("La corrección de texto no puede modificar montos")
        if self.reference.code is not CorrectionCode.FIX_TEXT and self.total <= 0:
            raise CorrectionError("La corrección de montos debe ser positiva")

    def line_amounts(self, line: FiscalLine):
        return calculate_line_amounts(line)

    @property
    def net_total(self) -> int:
        return sum(
            self.line_amounts(line).amount
            for line in self.lines
            if line.tax_category == TaxCategory.AFFECTED
        )

    @property
    def exempt_total(self) -> int:
        return sum(
            self.line_amounts(line).amount
            for line in self.lines
            if line.tax_category == TaxCategory.EXEMPT
        )

    @property
    def vat_total(self) -> int:
        return _clp(Decimal(self.net_total) * IVA_RATE)

    @property
    def total(self) -> int:
        return self.net_total + self.vat_total + self.exempt_total

    @property
    def issuer_rut(self) -> str:
        return self.issuer.rut

    @property
    def receiver_rut(self) -> str:
        return self.receiver.rut

    @property
    def receiver_name(self) -> str:
        return self.receiver.legal_name


def _end_of_following_month(value: date) -> date:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    return date(year, month, monthrange(year, month)[1])
