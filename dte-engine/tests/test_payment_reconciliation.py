import pytest

from completo_dte.application import (
    ElectronicPayment,
    PaymentMatchState,
    PaymentReconciliationService,
    SalePaymentExpectation,
    SiiEmissionModel,
)


def payment(*, sale_ref: str = "sale-1", amount: int = 11_900, reference: str = "ref-1"):
    return ElectronicPayment(
        provider="Transbank",
        terminal_id="POS-01",
        authorization_code="123456",
        provider_reference=reference,
        sale_ref=sale_ref,
        amount=amount,
        occurred_at="2026-07-12T13:00:00-04:00",
    )


def test_voucher_as_boleta_matches_without_creating_a_duplicate_dte() -> None:
    result = PaymentReconciliationService().reconcile(
        payments=(payment(),),
        sales=(SalePaymentExpectation("sale-1", 11_900, SiiEmissionModel.VOUCHER_AS_BOLETA),),
    )
    assert result.ready is True
    assert result.items[0].state is PaymentMatchState.MATCH
    assert "Voucher" in result.items[0].fiscal_evidence


def test_always_issue_requires_fiscal_document_and_amount_match() -> None:
    service = PaymentReconciliationService()
    missing = service.reconcile(
        payments=(payment(),),
        sales=(SalePaymentExpectation("sale-1", 11_900, SiiEmissionModel.ALWAYS_ISSUE),),
    )
    different = service.reconcile(
        payments=(payment(amount=10_000),),
        sales=(SalePaymentExpectation("sale-1", 11_900, SiiEmissionModel.ALWAYS_ISSUE, "39-1842"),),
    )
    assert missing.items[0].state is PaymentMatchState.FISCAL_DOCUMENT_MISSING
    assert different.items[0].state is PaymentMatchState.AMOUNT_DIFFERENCE


def test_unknown_sale_and_duplicate_voucher_are_not_silently_accepted() -> None:
    service = PaymentReconciliationService()
    unknown = service.reconcile(payments=(payment(),), sales=())
    assert unknown.items[0].state is PaymentMatchState.SALE_MISSING
    with pytest.raises(ValueError, match="duplicados"):
        service.reconcile(
            payments=(payment(), payment()),
            sales=(),
        )


def test_sale_without_voucher_blocks_reconciliation() -> None:
    result = PaymentReconciliationService().reconcile(
        payments=(),
        sales=(SalePaymentExpectation("sale-1", 11_900, SiiEmissionModel.VOUCHER_AS_BOLETA),),
    )
    assert result.ready is False
    assert result.items[0].state is PaymentMatchState.VOUCHER_MISSING
