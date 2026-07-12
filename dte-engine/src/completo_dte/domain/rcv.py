"""Modelo canónico de compras del Registro de Compras y Ventas."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from .fiscal_document import DocumentType
from .rut import normalize_rut


class RcvError(ValueError):
    """La fila o período RCV no es coherente."""


class RcvPurchaseStatus(StrEnum):
    PENDING = "pending"
    REGISTERED = "registered"
    CLAIMED = "claimed"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class RcvPeriod:
    year: int
    month: int

    def __post_init__(self) -> None:
        if not 2000 <= self.year <= 2100 or not 1 <= self.month <= 12:
            raise RcvError("Período RCV inválido")

    @property
    def key(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


@dataclass(frozen=True)
class RcvPurchaseEntry:
    issuer_rut: str
    document_type: DocumentType
    folio: int
    issued_on: date
    exempt_amount: int
    net_amount: int
    vat_amount: int
    total_amount: int
    status: RcvPurchaseStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "issuer_rut", normalize_rut(self.issuer_rut))
        if self.document_type not in {
            DocumentType.FACTURA_AFECTA,
            DocumentType.FACTURA_EXENTA,
            DocumentType.NOTA_DEBITO,
            DocumentType.NOTA_CREDITO,
        }:
            raise RcvError("Tipo documental no admitido en compras RCV iniciales")
        if self.folio <= 0:
            raise RcvError("Folio RCV inválido")
        amounts = (
            self.exempt_amount,
            self.net_amount,
            self.vat_amount,
            self.total_amount,
        )
        if any(amount < 0 for amount in amounts):
            raise RcvError("Los montos RCV no pueden ser negativos")
        if self.total_amount != self.exempt_amount + self.net_amount + self.vat_amount:
            raise RcvError("El total RCV no coincide con neto, exento e IVA")

    @property
    def identity(self) -> tuple[str, int, int]:
        return self.issuer_rut, int(self.document_type), self.folio
