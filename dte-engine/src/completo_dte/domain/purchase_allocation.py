"""Asignación operacional de líneas recibidas al control plane."""

from dataclasses import dataclass
from enum import StrEnum


class PurchaseDestination(StrEnum):
    EXPENSE = "expense"
    INVENTORY = "inventory"
    FIXED_ASSET = "fixed_asset"


@dataclass(frozen=True)
class PurchaseLineAllocation:
    line_number: int
    destination: PurchaseDestination
    control_plane_ref: str | None = None

    def __post_init__(self) -> None:
        if self.line_number <= 0:
            raise ValueError("Número de línea de compra inválido")
        if self.control_plane_ref is not None and (
            not self.control_plane_ref.strip() or len(self.control_plane_ref) > 200
        ):
            raise ValueError("Referencia operacional inválida")
