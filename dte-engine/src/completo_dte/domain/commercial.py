"""Objetos comerciales previos al DTE.

No son documentos tributarios: pueden evolucionar hasta que una conversión
explícita origine una guía o DTE inmutable.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum


class CommercialDocumentKind(StrEnum):
    QUOTE = "quote"
    SALES_ORDER = "sales_order"
    PURCHASE_ORDER = "purchase_order"


class CommercialDocumentStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    CONVERTED = "converted"


@dataclass(frozen=True)
class CommercialLine:
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount_percent: Decimal = Decimal("0")
    product_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.description.strip() or len(self.description) > 200:
            raise ValueError("La descripción comercial es obligatoria")
        if self.quantity <= 0 or self.unit_price < 0:
            raise ValueError("Cantidad y precio comercial inválidos")
        if not Decimal("0") <= self.discount_percent <= Decimal("100"):
            raise ValueError("El descuento debe estar entre 0 y 100")

    @property
    def subtotal(self) -> int:
        value = self.quantity * self.unit_price * (
            Decimal("1") - self.discount_percent / Decimal("100")
        )
        return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class CommercialDocument:
    kind: CommercialDocumentKind
    branch_id: str
    counterparty_ref: str
    counterparty_name: str
    issued_on: date
    valid_until: date | None
    currency: str
    lines: tuple[CommercialLine, ...]
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.branch_id.strip() or not self.counterparty_ref.strip():
            raise ValueError("Sucursal y contraparte son obligatorias")
        if not self.counterparty_name.strip() or len(self.counterparty_name) > 120:
            raise ValueError("La contraparte es obligatoria")
        if self.currency != "CLP":
            raise ValueError("V1 sólo admite CLP")
        if not self.lines:
            raise ValueError("El documento comercial requiere líneas")
        if self.valid_until is not None and self.valid_until < self.issued_on:
            raise ValueError("La vigencia no puede terminar antes de la emisión")

    @property
    def total(self) -> int:
        return sum(line.subtotal for line in self.lines)
