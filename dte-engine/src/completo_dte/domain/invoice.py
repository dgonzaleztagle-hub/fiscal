"""Reglas tributarias y totales para facturas comunes tipos 33 y 34."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .boleta import IVA_RATE, MAX_ISSUE_DATE, Issuer
from .fiscal_document import (
    DocumentType,
    FiscalDocumentDraft,
    FiscalLine,
    Party,
    PaymentTerms,
    PriceMode,
    TaxCategory,
)

MIN_INVOICE_ISSUE_DATE = date(2003, 4, 1)


class InvoiceError(ValueError):
    """La operación no se puede representar como factura 33/34."""


@dataclass(frozen=True)
class InvoiceLineAmounts:
    amount: int
    discount: int
    surcharge: int


@dataclass(frozen=True)
class Invoice:
    issuer: Issuer
    receiver: Party
    document_type: DocumentType
    folio: int
    issued_on: date
    lines: tuple[FiscalLine, ...]
    payment_terms: PaymentTerms = PaymentTerms.CASH
    due_on: date | None = None

    def __post_init__(self) -> None:
        if self.document_type not in {
            DocumentType.FACTURA_AFECTA,
            DocumentType.FACTURA_EXENTA,
        }:
            raise InvoiceError("Invoice sólo admite facturas tipos 33 y 34")
        if not 1 <= self.folio <= 9_999_999_999:
            raise InvoiceError("El folio debe estar entre 1 y 9999999999")
        if not MIN_INVOICE_ISSUE_DATE <= self.issued_on <= MAX_ISSUE_DATE:
            raise InvoiceError("Fecha de emisión fuera del rango admitido")
        if not 1 <= len(self.lines) <= 60:
            raise InvoiceError("La factura debe contener entre 1 y 60 ítems")
        for value, label, maximum in (
            (self.receiver.business_activity, "giro del receptor", 40),
            (self.receiver.address, "dirección del receptor", 70),
            (self.receiver.commune, "comuna del receptor", 20),
        ):
            if value is None:
                raise InvoiceError(f"La factura requiere {label}")
            if len(value.encode("iso-8859-1")) > maximum:
                raise InvoiceError(f"{label.capitalize()} excede {maximum} bytes")
        if any(line.tax_category == TaxCategory.NON_BILLABLE for line in self.lines):
            raise InvoiceError("La primera versión de facturas no admite líneas no facturables")
        if any(
            line.tax_category == TaxCategory.AFFECTED and line.price_mode != PriceMode.NET
            for line in self.lines
        ):
            raise InvoiceError("Las líneas afectas de factura deben informar precio neto")
        if self.document_type == DocumentType.FACTURA_EXENTA and any(
            line.tax_category != TaxCategory.EXEMPT for line in self.lines
        ):
            raise InvoiceError("La factura 34 sólo admite líneas exentas")
        if self.document_type == DocumentType.FACTURA_AFECTA and not any(
            line.tax_category == TaxCategory.AFFECTED for line in self.lines
        ):
            raise InvoiceError("La factura 33 requiere al menos una línea afecta")
        if self.payment_terms == PaymentTerms.CREDIT and self.due_on is None:
            raise InvoiceError("Una factura a crédito debe indicar vencimiento")
        if self.due_on is not None and self.due_on < self.issued_on:
            raise InvoiceError("El vencimiento no puede ser anterior a la emisión")
        if self.total <= 0:
            raise InvoiceError("El total de la factura debe ser positivo")

    @classmethod
    def from_draft(
        cls,
        draft: FiscalDocumentDraft,
        *,
        issuer: Issuer,
        folio: int,
    ) -> "Invoice":
        if draft.receiver is None:
            raise InvoiceError("La factura requiere receptor")
        return cls(
            issuer=issuer,
            receiver=draft.receiver,
            document_type=draft.document_type,
            folio=folio,
            issued_on=draft.issued_on,
            lines=draft.lines,
            payment_terms=draft.payment_terms or PaymentTerms.CASH,
            due_on=draft.due_on,
        )

    def line_amounts(self, line: FiscalLine) -> InvoiceLineAmounts:
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


def calculate_line_amounts(line: FiscalLine) -> InvoiceLineAmounts:
    raw = line.quantity * line.unit_price
    discount = (
        raw * line.discount_percent / Decimal(100)
        if line.discount_percent
        else line.discount_amount
    )
    surcharge = (
        raw * line.surcharge_percent / Decimal(100)
        if line.surcharge_percent
        else line.surcharge_amount
    )
    if discount > raw:
        raise InvoiceError("El descuento no puede superar el monto base del ítem")
    adjusted = raw - discount + surcharge
    return InvoiceLineAmounts(
        amount=_clp(adjusted),
        discount=_clp(discount),
        surcharge=_clp(surcharge),
    )


def _clp(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
