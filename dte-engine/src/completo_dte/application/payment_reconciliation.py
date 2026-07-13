"""Conciliación de pagos electrónicos sin confundir voucher, venta y DTE."""

from dataclasses import dataclass
from enum import StrEnum


class SiiEmissionModel(StrEnum):
    ALWAYS_ISSUE = "always_issue"
    VOUCHER_AS_BOLETA = "voucher_as_boleta"


class PaymentMatchState(StrEnum):
    MATCH = "match"
    AMOUNT_DIFFERENCE = "amount_difference"
    SALE_MISSING = "sale_missing"
    FISCAL_DOCUMENT_MISSING = "fiscal_document_missing"
    VOUCHER_MISSING = "voucher_missing"


@dataclass(frozen=True)
class ElectronicPayment:
    provider: str
    terminal_id: str
    authorization_code: str
    provider_reference: str
    sale_ref: str
    amount: int
    occurred_at: str
    settlement_ref: str | None = None

    def __post_init__(self) -> None:
        for value in (
            self.provider,
            self.terminal_id,
            self.authorization_code,
            self.provider_reference,
            self.sale_ref,
            self.occurred_at,
        ):
            if not value.strip():
                raise ValueError("El voucher contiene identificadores vacíos")
        if self.amount <= 0:
            raise ValueError("El monto del voucher debe ser positivo")

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (
            self.provider,
            self.terminal_id,
            self.authorization_code,
            self.provider_reference,
        )


@dataclass(frozen=True)
class SalePaymentExpectation:
    sale_ref: str
    amount: int
    emission_model: SiiEmissionModel
    fiscal_document_ref: str | None = None


@dataclass(frozen=True)
class PaymentReconciliationItem:
    payment: ElectronicPayment | None
    sale: SalePaymentExpectation | None
    state: PaymentMatchState
    detail: str
    fiscal_evidence: str


@dataclass(frozen=True)
class PaymentReconciliation:
    items: tuple[PaymentReconciliationItem, ...]

    @property
    def ready(self) -> bool:
        return all(item.state is PaymentMatchState.MATCH for item in self.items)

    @property
    def total(self) -> int:
        return sum(item.payment.amount for item in self.items if item.payment is not None)


class PaymentReconciliationService:
    def reconcile(
        self,
        *,
        payments: tuple[ElectronicPayment, ...],
        sales: tuple[SalePaymentExpectation, ...],
    ) -> PaymentReconciliation:
        identities = [payment.identity for payment in payments]
        if len(identities) != len(set(identities)):
            raise ValueError("La importación contiene vouchers duplicados")
        sales_by_ref = {sale.sale_ref: sale for sale in sales}
        if len(sales_by_ref) != len(sales):
            raise ValueError("Las ventas contienen referencias duplicadas")
        items = []
        for payment in payments:
            sale = sales_by_ref.get(payment.sale_ref)
            if sale is None:
                items.append(
                    PaymentReconciliationItem(
                        payment, None,
                        PaymentMatchState.SALE_MISSING,
                        "El voucher no tiene una venta conocida",
                        "Sin evidencia fiscal resuelta",
                    )
                )
                continue
            if sale.amount != payment.amount:
                items.append(
                    PaymentReconciliationItem(
                        payment, sale,
                        PaymentMatchState.AMOUNT_DIFFERENCE,
                        f"Voucher ${payment.amount} frente a venta ${sale.amount}",
                        _fiscal_evidence(sale),
                    )
                )
                continue
            if (
                sale.emission_model is SiiEmissionModel.ALWAYS_ISSUE
                and sale.fiscal_document_ref is None
            ):
                items.append(
                    PaymentReconciliationItem(
                        payment, sale,
                        PaymentMatchState.FISCAL_DOCUMENT_MISSING,
                        "El modelo del tenant exige boleta y aún no existe",
                        "Boleta pendiente",
                    )
                )
                continue
            items.append(
                PaymentReconciliationItem(
                    payment, sale,
                    PaymentMatchState.MATCH,
                    "Monto y venta coinciden",
                    _fiscal_evidence(sale),
                )
            )
        payments_by_sale = {payment.sale_ref for payment in payments}
        for sale in sales:
            if sale.sale_ref not in payments_by_sale:
                items.append(
                    PaymentReconciliationItem(
                        None, sale, PaymentMatchState.VOUCHER_MISSING,
                        "La venta no tiene voucher electrónico asociado",
                        _fiscal_evidence(sale),
                    )
                )
        return PaymentReconciliation(tuple(items))


def _fiscal_evidence(sale: SalePaymentExpectation) -> str:
    if sale.emission_model is SiiEmissionModel.VOUCHER_AS_BOLETA:
        return "Voucher autorizado como respaldo de la venta"
    return f"DTE {sale.fiscal_document_ref}" if sale.fiscal_document_ref else "Boleta pendiente"
