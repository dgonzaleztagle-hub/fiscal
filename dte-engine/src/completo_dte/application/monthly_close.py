"""Cierre mensual determinista derivado de evidencia fiscal versionada."""

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
from types import MappingProxyType
from typing import Mapping

from .monthly_report import MonthlyDocumentRow, MonthlyFiscalReport


FORMULA_VERSION = "plus-baseline-2026-07-v1"


class CloseDifferenceState(StrEnum):
    MATCH = "match"
    DIFFERENT = "different"
    NOT_COMPARED = "not_compared"


@dataclass(frozen=True)
class MonthlyCloseInputs:
    prior_vat_credit: int = 0
    subject_change_credit: int = 0
    subject_change_debit: int = 0
    ppm_rate_basis_points: int = 0
    second_category_withholding: int = 0
    single_tax: int = 0
    additional_withholding: int = 0
    other_taxes: Mapping[str, int] = field(default_factory=dict)
    late_surcharge: int = 0
    condonation: int = 0
    sii_proposal: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        scalar_values = (
            self.prior_vat_credit,
            self.subject_change_credit,
            self.subject_change_debit,
            self.ppm_rate_basis_points,
            self.second_category_withholding,
            self.single_tax,
            self.additional_withholding,
            self.late_surcharge,
            self.condonation,
        )
        if any(value < 0 for value in scalar_values):
            raise ValueError("Los ajustes del cierre no pueden ser negativos")
        if self.ppm_rate_basis_points > 10_000:
            raise ValueError("La tasa PPM no puede superar 100%")
        if any(value < 0 for value in self.other_taxes.values()):
            raise ValueError("Los otros impuestos no pueden ser negativos")
        object.__setattr__(self, "other_taxes", MappingProxyType(dict(self.other_taxes)))
        object.__setattr__(self, "sii_proposal", MappingProxyType(dict(self.sii_proposal)))


@dataclass(frozen=True)
class MonthlyCloseLine:
    code: str
    label: str
    amount: int
    sii_amount: int | None
    difference: int | None
    state: CloseDifferenceState


@dataclass(frozen=True)
class MonthlyCloseSnapshot:
    period: str
    formula_version: str
    source_hash: str
    calculation_hash: str
    sales_net: int
    sales_exempt: int
    sales_vat: int
    sales_total: int
    purchases_net: int
    purchases_exempt: int
    purchases_vat: int
    purchases_total: int
    ppm_basis: int
    ppm: int
    vat_payable: int
    next_vat_credit: int
    total_payable: int
    lines: tuple[MonthlyCloseLine, ...]


class MonthlyCloseCalculator:
    """Calcula una propuesta explicable; no presenta ni rectifica un F29."""

    def calculate(
        self,
        report: MonthlyFiscalReport,
        inputs: MonthlyCloseInputs = MonthlyCloseInputs(),
    ) -> MonthlyCloseSnapshot:
        sales = _totals(report.rows, "sale")
        purchases = _totals(report.rows, "purchase")
        ppm_basis = max(0, sales["net"] + sales["exempt"])
        ppm = _round_ratio(ppm_basis * inputs.ppm_rate_basis_points, 10_000)

        available_credit = (
            purchases["vat"]
            + inputs.prior_vat_credit
            + inputs.subject_change_credit
        )
        debit = sales["vat"] + inputs.subject_change_debit
        vat_balance = debit - available_credit
        vat_payable = max(0, vat_balance)
        next_vat_credit = max(0, -vat_balance)
        other_taxes_total = sum(inputs.other_taxes.values())
        obligations = (
            vat_payable
            + ppm
            + inputs.second_category_withholding
            + inputs.single_tax
            + inputs.additional_withholding
            + other_taxes_total
            + inputs.late_surcharge
        )
        total_payable = max(0, obligations - inputs.condonation)

        amounts = {
            "sales_vat": sales["vat"],
            "purchase_vat": purchases["vat"],
            "prior_vat_credit": inputs.prior_vat_credit,
            "subject_change_credit": inputs.subject_change_credit,
            "subject_change_debit": inputs.subject_change_debit,
            "ppm": ppm,
            "second_category_withholding": inputs.second_category_withholding,
            "single_tax": inputs.single_tax,
            "additional_withholding": inputs.additional_withholding,
            "other_taxes": other_taxes_total,
            "late_surcharge": inputs.late_surcharge,
            "condonation": inputs.condonation,
            "vat_payable": vat_payable,
            "next_vat_credit": next_vat_credit,
            "total_payable": total_payable,
        }
        labels = {
            "sales_vat": "Débito fiscal por ventas",
            "purchase_vat": "Crédito fiscal por compras",
            "prior_vat_credit": "Remanente de crédito anterior",
            "subject_change_credit": "Cambio de sujeto a favor",
            "subject_change_debit": "Cambio de sujeto retenido",
            "ppm": "Pago provisional mensual",
            "second_category_withholding": "Retención de segunda categoría",
            "single_tax": "Impuesto único",
            "additional_withholding": "Retenciones adicionales",
            "other_taxes": "Otros impuestos",
            "late_surcharge": "Recargos por atraso",
            "condonation": "Condonación",
            "vat_payable": "IVA determinado",
            "next_vat_credit": "Remanente para el período siguiente",
            "total_payable": "Pago total estimado",
        }
        lines = tuple(
            _line(code, labels[code], amount, inputs.sii_proposal)
            for code, amount in amounts.items()
        )
        source_hash = _source_hash(report)
        calculation_payload = {
            "period": report.period,
            "formula_version": FORMULA_VERSION,
            "source_hash": source_hash,
            "inputs": _input_payload(inputs),
            "amounts": amounts,
        }
        calculation_hash = hashlib.sha256(
            json.dumps(calculation_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return MonthlyCloseSnapshot(
            period=report.period,
            formula_version=FORMULA_VERSION,
            source_hash=source_hash,
            calculation_hash=calculation_hash,
            sales_net=sales["net"],
            sales_exempt=sales["exempt"],
            sales_vat=sales["vat"],
            sales_total=sales["total"],
            purchases_net=purchases["net"],
            purchases_exempt=purchases["exempt"],
            purchases_vat=purchases["vat"],
            purchases_total=purchases["total"],
            ppm_basis=ppm_basis,
            ppm=ppm,
            vat_payable=vat_payable,
            next_vat_credit=next_vat_credit,
            total_payable=total_payable,
            lines=lines,
        )


def _totals(rows: tuple[MonthlyDocumentRow, ...], direction: str) -> dict[str, int]:
    totals = {"net": 0, "exempt": 0, "vat": 0, "total": 0}
    for row in rows:
        if row.direction != direction:
            continue
        sign = -1 if row.document_type == 61 else 1
        for key in totals:
            totals[key] += sign * getattr(row, key)
    return totals


def _round_ratio(numerator: int, denominator: int) -> int:
    quotient, remainder = divmod(numerator, denominator)
    return quotient + (1 if remainder * 2 >= denominator else 0)


def _line(
    code: str, label: str, amount: int, proposal: Mapping[str, int]
) -> MonthlyCloseLine:
    if code not in proposal:
        return MonthlyCloseLine(
            code, label, amount, None, None, CloseDifferenceState.NOT_COMPARED
        )
    sii_amount = proposal[code]
    difference = amount - sii_amount
    return MonthlyCloseLine(
        code,
        label,
        amount,
        sii_amount,
        difference,
        CloseDifferenceState.MATCH if difference == 0 else CloseDifferenceState.DIFFERENT,
    )


def _source_hash(report: MonthlyFiscalReport) -> str:
    payload = [
        {
            "direction": row.direction,
            "document_type": row.document_type,
            "folio": row.folio,
            "taxpayer_rut": row.taxpayer_rut,
            "issued_on": row.issued_on,
            "net": row.net,
            "exempt": row.exempt,
            "vat": row.vat,
            "total": row.total,
            "xml_sha256": row.xml_sha256,
        }
        for row in report.rows
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _input_payload(inputs: MonthlyCloseInputs) -> dict[str, object]:
    return {
        "prior_vat_credit": inputs.prior_vat_credit,
        "subject_change_credit": inputs.subject_change_credit,
        "subject_change_debit": inputs.subject_change_debit,
        "ppm_rate_basis_points": inputs.ppm_rate_basis_points,
        "second_category_withholding": inputs.second_category_withholding,
        "single_tax": inputs.single_tax,
        "additional_withholding": inputs.additional_withholding,
        "other_taxes": dict(sorted(inputs.other_taxes.items())),
        "late_surcharge": inputs.late_surcharge,
        "condonation": inputs.condonation,
        "sii_proposal": dict(sorted(inputs.sii_proposal.items())),
    }
