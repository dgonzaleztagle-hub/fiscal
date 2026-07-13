"""Contrato mensual mínimo entre Completo Personas y Fiscal."""

from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class PeopleMonthlySummary:
    period: str
    worker_count: int
    taxable_payroll: int
    pension_obligations: int
    single_tax: int
    other_withholdings: int
    source_version: str

    def __post_init__(self) -> None:
        if len(self.period) != 7 or self.period[4] != "-":
            raise ValueError("Período Personas inválido")
        if self.worker_count < 0 or any(value < 0 for value in (
            self.taxable_payroll, self.pension_obligations,
            self.single_tax, self.other_withholdings,
        )):
            raise ValueError("El resumen Personas no admite valores negativos")
        if not self.source_version.strip():
            raise ValueError("El resumen Personas requiere versión de origen")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(json.dumps(self.__dict__, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
