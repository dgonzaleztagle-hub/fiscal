"""Modelo mínimo de una boleta afecta con precios brutos."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .rut import normalize_rut

IVA_RATE = Decimal("0.19")
MIN_ISSUE_DATE = date(2002, 8, 1)
MAX_ISSUE_DATE = date(2050, 12, 31)


class BoletaError(ValueError):
    """La venta no se puede representar como boleta tipo 39."""


@dataclass(frozen=True)
class Issuer:
    rut: str
    legal_name: str
    business_activity: str
    activity_code: int
    address: str | None = None
    commune: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rut", normalize_rut(self.rut))
        _require_latin1_length(self.legal_name, "razón social del emisor", 1, 100)
        _require_latin1_length(self.business_activity, "giro del emisor", 1, 80)
        if not 1 <= self.activity_code <= 999_999:
            raise BoletaError("El código de actividad económica debe tener hasta 6 dígitos")
        if self.address is not None:
            _require_latin1_length(self.address, "dirección del emisor", 1, 70)
        if self.commune is not None:
            _require_latin1_length(self.commune, "comuna del emisor", 1, 20)


@dataclass(frozen=True)
class BoletaLine:
    name: str
    quantity: Decimal
    unit_price_gross: Decimal
    discount_gross: Decimal = Decimal(0)
    is_exempt: bool = False
    unit_measure: str | None = None

    def __post_init__(self) -> None:
        cleaned = " ".join(self.name.split())
        if not cleaned or len(cleaned.encode("iso-8859-1", errors="replace")) > 80:
            raise BoletaError("El nombre del ítem debe ocupar entre 1 y 80 bytes")
        if self.quantity <= 0 or self.unit_price_gross < 0 or self.discount_gross < 0:
            raise BoletaError("Cantidad y montos del ítem no pueden ser negativos")
        if self.discount_gross > self.quantity * self.unit_price_gross:
            raise BoletaError("El descuento no puede superar el monto bruto del ítem")
        if self.unit_measure is not None:
            _require_latin1_length(self.unit_measure, "unidad de medida", 1, 4)
        object.__setattr__(self, "name", cleaned)

    @property
    def gross_total(self) -> int:
        amount = self.quantity * self.unit_price_gross - self.discount_gross
        return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class BoletaAfecta:
    issuer: Issuer
    folio: int
    issued_on: date
    lines: tuple[BoletaLine, ...]
    receiver_rut: str = "66666666-6"
    receiver_name: str = "SIN INFORMACION"
    service_indicator: int = 3
    reference_code: str | None = None
    reference_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "receiver_rut", normalize_rut(self.receiver_rut))
        if not 1 <= self.folio <= 9_999_999_999:
            raise BoletaError("El folio debe estar entre 1 y 9999999999")
        if not 1 <= len(self.lines) <= 60:
            raise BoletaError("La boleta debe contener entre 1 y 60 ítems")
        if not MIN_ISSUE_DATE <= self.issued_on <= MAX_ISSUE_DATE:
            raise BoletaError(
                "La fecha de emisión debe estar entre 2002-08-01 y 2050-12-31"
            )
        if self.service_indicator != 3:
            raise BoletaError("El primer spike sólo admite venta y servicios no periódicos")
        if len(self.receiver_name.encode("iso-8859-1", errors="replace")) > 40:
            raise BoletaError("La razón social del receptor excede 40 bytes")
        if (self.reference_code is None) != (self.reference_reason is None):
            raise BoletaError("Código y razón de referencia deben informarse juntos")
        if self.reference_code is not None:
            _require_latin1_length(self.reference_code, "código de referencia", 1, 18)
            _require_latin1_length(self.reference_reason, "razón de referencia", 1, 90)
        if self.total <= 0:
            raise BoletaError("El monto total de la boleta debe ser positivo")
        if self.affected_gross_total <= 0:
            raise BoletaError("La boleta tipo 39 debe contener al menos un ítem afecto")

    @property
    def total(self) -> int:
        return sum(line.gross_total for line in self.lines)

    @property
    def exempt_total(self) -> int:
        return sum(line.gross_total for line in self.lines if line.is_exempt)

    @property
    def affected_gross_total(self) -> int:
        return sum(line.gross_total for line in self.lines if not line.is_exempt)

    @property
    def net_total(self) -> int:
        net = Decimal(self.affected_gross_total) / (Decimal(1) + IVA_RATE)
        return int(net.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @property
    def vat_total(self) -> int:
        return self.affected_gross_total - self.net_total

    @property
    def issuer_rut(self) -> str:
        return self.issuer.rut

    @property
    def document_type(self) -> int:
        return 39


@dataclass(frozen=True)
class BoletaExenta:
    """Boleta tipo 41: todos sus ítems y su total son exentos."""

    issuer: Issuer
    folio: int
    issued_on: date
    lines: tuple[BoletaLine, ...]
    receiver_rut: str = "66666666-6"
    receiver_name: str = "SIN INFORMACION"
    service_indicator: int = 3
    reference_code: str | None = None
    reference_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "receiver_rut", normalize_rut(self.receiver_rut))
        if not 1 <= self.folio <= 9_999_999_999:
            raise BoletaError("El folio debe estar entre 1 y 9999999999")
        if not 1 <= len(self.lines) <= 60:
            raise BoletaError("La boleta debe contener entre 1 y 60 ítems")
        if not MIN_ISSUE_DATE <= self.issued_on <= MAX_ISSUE_DATE:
            raise BoletaError(
                "La fecha de emisión debe estar entre 2002-08-01 y 2050-12-31"
            )
        if self.service_indicator != 3:
            raise BoletaError("La boleta exenta sólo admite venta y servicios no periódicos")
        if len(self.receiver_name.encode("iso-8859-1", errors="replace")) > 40:
            raise BoletaError("La razón social del receptor excede 40 bytes")
        if (self.reference_code is None) != (self.reference_reason is None):
            raise BoletaError("Código y razón de referencia deben informarse juntos")
        if self.reference_code is not None:
            _require_latin1_length(self.reference_code, "código de referencia", 1, 18)
            _require_latin1_length(self.reference_reason, "razón de referencia", 1, 90)
        if any(not line.is_exempt for line in self.lines):
            raise BoletaError("La boleta tipo 41 sólo puede contener ítems exentos")
        if self.total <= 0:
            raise BoletaError("El monto total de la boleta debe ser positivo")

    @property
    def total(self) -> int:
        return sum(line.gross_total for line in self.lines)

    @property
    def exempt_total(self) -> int:
        return self.total

    @property
    def affected_gross_total(self) -> int:
        return 0

    @property
    def net_total(self) -> int:
        return 0

    @property
    def vat_total(self) -> int:
        return 0

    @property
    def issuer_rut(self) -> str:
        return self.issuer.rut

    @property
    def document_type(self) -> int:
        return 41


def _require_latin1_length(value: str, label: str, minimum: int, maximum: int) -> None:
    try:
        length = len(value.encode("iso-8859-1"))
    except UnicodeEncodeError as exc:
        raise BoletaError(f"{label.capitalize()} contiene caracteres fuera de ISO-8859-1") from exc
    if not minimum <= length <= maximum:
        raise BoletaError(f"{label.capitalize()} debe ocupar entre {minimum} y {maximum} bytes")
