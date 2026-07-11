"""Reglas tributarias para guías de despacho electrónicas tipo 52."""

from dataclasses import dataclass
from datetime import date, time
from enum import IntEnum
from decimal import Decimal

from .boleta import IVA_RATE, MAX_ISSUE_DATE, Issuer
from .fiscal_document import (
    DispatchReason,
    FiscalDocumentDraft,
    FiscalLine,
    Party,
    PriceMode,
    TaxCategory,
)
from .invoice import _clp, calculate_line_amounts
from .rut import normalize_rut


class DispatchError(ValueError):
    """La operación no se puede representar como guía 52."""


class DispatchAccount(IntEnum):
    """Quién soporta el despacho según ``TipoDespacho`` del SII."""

    BUYER = 1
    ISSUER_TO_BUYER = 2
    ISSUER_TO_OTHER = 3


@dataclass(frozen=True)
class DispatchTransport:
    vehicle_plate: str | None = None
    carrier_rut: str | None = None
    driver_rut: str | None = None
    driver_name: str | None = None
    destination_address: str | None = None
    destination_commune: str | None = None
    destination_city: str | None = None
    # Resolución 154/2025, postergada por Res. 52/2026. El XSD vigente aún no
    # contiene estos elementos; se modelan para migrar sin perder contrato.
    trailer_plate: str | None = None
    departure_on: date | None = None
    departure_time: time | None = None
    arrival_on: date | None = None

    def __post_init__(self) -> None:
        if self.carrier_rut is not None:
            object.__setattr__(self, "carrier_rut", normalize_rut(self.carrier_rut))
        if self.driver_rut is not None:
            object.__setattr__(self, "driver_rut", normalize_rut(self.driver_rut))
        for value, label, maximum in (
            (self.vehicle_plate, "patente", 8),
            (self.driver_name, "nombre del chofer", 30),
            (self.destination_address, "dirección de destino", 70),
            (self.destination_commune, "comuna de destino", 20),
            (self.destination_city, "ciudad de destino", 20),
            (self.trailer_plate, "patente del carro", 8),
        ):
            if value is not None and not 1 <= len(value.encode("iso-8859-1")) <= maximum:
                raise DispatchError(f"{label.capitalize()} excede {maximum} bytes")
        if (self.driver_rut is None) != (self.driver_name is None):
            raise DispatchError("RUT y nombre del chofer deben informarse juntos")

    @property
    def has_future_fields(self) -> bool:
        return any(
            value is not None
            for value in (
                self.trailer_plate,
                self.departure_on,
                self.departure_time,
                self.arrival_on,
            )
        )


@dataclass(frozen=True)
class DispatchDocument:
    issuer: Issuer
    receiver: Party
    folio: int
    issued_on: date
    reason: DispatchReason
    lines: tuple[FiscalLine, ...]
    transport: DispatchTransport
    dispatch_account: DispatchAccount | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.folio <= 9_999_999_999:
            raise DispatchError("Folio de guía inválido")
        if not date(2003, 4, 1) <= self.issued_on <= MAX_ISSUE_DATE:
            raise DispatchError("Fecha de guía fuera de rango")
        if not 1 <= len(self.lines) <= 60:
            raise DispatchError("La guía debe contener entre 1 y 60 ítems")
        if any(
            value is None
            for value in (
                self.receiver.business_activity,
                self.receiver.address,
                self.receiver.commune,
            )
        ):
            raise DispatchError("La guía requiere giro, dirección y comuna del receptor")
        if self.reason is DispatchReason.INTERNAL_TRANSFER:
            if self.receiver.rut != self.issuer.rut:
                raise DispatchError("El traslado interno debe usar al emisor como receptor")
            if self.dispatch_account is not None:
                raise DispatchError("El traslado interno no informa TipoDespacho")
        elif self.dispatch_account is None:
            raise DispatchError("La guía debe indicar por cuenta de quién se despacha")
        non_billable = [line.tax_category is TaxCategory.NON_BILLABLE for line in self.lines]
        if any(non_billable) and not all(non_billable):
            raise DispatchError("Una guía no puede mezclar ítems valorizados y no valorizados")
        if all(non_billable):
            if any(line.unit_price != 0 for line in self.lines):
                raise DispatchError("Los ítems no valorizados deben tener precio cero")
            if any(
                line.discount_percent
                or line.discount_amount
                or line.surcharge_percent
                or line.surcharge_amount
                for line in self.lines
            ):
                raise DispatchError("Un ítem no valorizado no admite descuentos ni recargos")
        elif any(
            line.tax_category is TaxCategory.AFFECTED and line.price_mode is not PriceMode.NET
            for line in self.lines
        ):
            raise DispatchError("Las líneas afectas de guía deben informar precio neto")

    @classmethod
    def from_draft(
        cls,
        draft: FiscalDocumentDraft,
        *,
        issuer: Issuer,
        folio: int,
        transport: DispatchTransport,
        dispatch_account: DispatchAccount | None,
    ) -> "DispatchDocument":
        if draft.receiver is None or draft.dispatch_reason is None:
            raise DispatchError("La guía requiere receptor y motivo del traslado")
        return cls(
            issuer=issuer,
            receiver=draft.receiver,
            folio=folio,
            issued_on=draft.issued_on,
            reason=draft.dispatch_reason,
            lines=draft.lines,
            transport=transport,
            dispatch_account=dispatch_account,
        )

    @property
    def document_type(self) -> int:
        return 52

    @property
    def is_valued(self) -> bool:
        return self.lines[0].tax_category is not TaxCategory.NON_BILLABLE

    def line_amount(self, line: FiscalLine) -> int:
        return calculate_line_amounts(line).amount if self.is_valued else 0

    @property
    def net_total(self) -> int:
        return sum(
            self.line_amount(line)
            for line in self.lines
            if line.tax_category is TaxCategory.AFFECTED
        )

    @property
    def exempt_total(self) -> int:
        return sum(
            self.line_amount(line)
            for line in self.lines
            if line.tax_category is TaxCategory.EXEMPT
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
