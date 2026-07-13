import dataclasses

import pytest

from completo_dte.application import (
    CloseDifferenceState,
    MonthlyCloseCalculator,
    MonthlyCloseInputs,
    MonthlyDocumentRow,
    MonthlyFiscalReport,
)


def row(direction: str, document_type: int, folio: int, net: int, exempt: int, vat: int, total: int) -> MonthlyDocumentRow:
    return MonthlyDocumentRow(
        direction=direction,
        document_type=document_type,
        folio=folio,
        taxpayer_rut="76.192.083-9",
        issued_on="2026-07-10",
        net=net,
        exempt=exempt,
        vat=vat,
        total=total,
        xml_sha256=f"{folio:064x}",
    )


def plus_baseline_report() -> MonthlyFiscalReport:
    return MonthlyFiscalReport(
        "2026-07",
        (
            row("sale", 33, 1, 1_000_000, 0, 190_000, 1_190_000),
            row("sale", 39, 2, 100_000, 0, 19_000, 119_000),
            row("sale", 41, 3, 0, 50_000, 0, 50_000),
            row("sale", 56, 4, 10_000, 0, 1_900, 11_900),
            row("sale", 61, 5, 100_000, 0, 19_000, 119_000),
            row("purchase", 33, 10, 400_000, 0, 76_000, 476_000),
            row("purchase", 34, 11, 0, 80_000, 0, 80_000),
            row("purchase", 61, 12, 20_000, 0, 3_800, 23_800),
        ),
    )


def test_plus_baseline_handles_notes_carry_ppm_withholdings_and_taxes() -> None:
    snapshot = MonthlyCloseCalculator().calculate(
        plus_baseline_report(),
        MonthlyCloseInputs(
            prior_vat_credit=25_000,
            subject_change_credit=2_000,
            subject_change_debit=3_000,
            ppm_rate_basis_points=100,
            second_category_withholding=6_863,
            single_tax=4_000,
            additional_withholding=1_000,
            other_taxes={"bebidas": 2_500, "combustibles": 1_500},
            late_surcharge=5_000,
            condonation=2_000,
        ),
    )

    assert snapshot.sales_net == 1_010_000
    assert snapshot.sales_exempt == 50_000
    assert snapshot.sales_vat == 191_900
    assert snapshot.purchases_net == 380_000
    assert snapshot.purchases_exempt == 80_000
    assert snapshot.purchases_vat == 72_200
    assert snapshot.ppm_basis == 1_060_000
    assert snapshot.ppm == 10_600
    assert snapshot.vat_payable == 95_700
    assert snapshot.next_vat_credit == 0
    assert snapshot.total_payable == 125_163


def test_close_is_deterministic_and_exposes_semantic_sii_difference() -> None:
    inputs = MonthlyCloseInputs(
        ppm_rate_basis_points=100,
        sii_proposal={"sales_vat": 191_900, "purchase_vat": 70_000},
    )
    first = MonthlyCloseCalculator().calculate(plus_baseline_report(), inputs)
    second = MonthlyCloseCalculator().calculate(plus_baseline_report(), inputs)

    assert first.source_hash == second.source_hash
    assert first.calculation_hash == second.calculation_hash
    line_by_code = {line.code: line for line in first.lines}
    assert line_by_code["sales_vat"].state is CloseDifferenceState.MATCH
    assert line_by_code["purchase_vat"].state is CloseDifferenceState.DIFFERENT
    assert line_by_code["purchase_vat"].difference == 2_200
    assert line_by_code["ppm"].state is CloseDifferenceState.NOT_COMPARED


def test_credit_surplus_is_carried_and_never_creates_negative_payment() -> None:
    snapshot = MonthlyCloseCalculator().calculate(
        MonthlyFiscalReport(
            "2026-07",
            (row("sale", 33, 1, 100_000, 0, 19_000, 119_000),),
        ),
        MonthlyCloseInputs(prior_vat_credit=30_000),
    )
    assert snapshot.vat_payable == 0
    assert snapshot.next_vat_credit == 11_000
    assert snapshot.total_payable == 0


def test_inputs_reject_negative_amounts_and_are_immutable() -> None:
    with pytest.raises(ValueError):
        MonthlyCloseInputs(prior_vat_credit=-1)
    inputs = MonthlyCloseInputs(other_taxes={"bebidas": 100})
    with pytest.raises(TypeError):
        inputs.other_taxes["bebidas"] = 200
    with pytest.raises(dataclasses.FrozenInstanceError):
        inputs.prior_vat_credit = 1
