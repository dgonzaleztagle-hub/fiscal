"""Importación y conciliación tenant-first de pagos electrónicos."""

from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from completo_dte.application import (
    ElectronicPayment,
    PaymentReconciliationService,
    SalePaymentExpectation,
    SiiEmissionModel,
    PeopleMonthlySummary,
)
from completo_dte.infrastructure import FolioLedger, FolioLedgerError

from .security import ApiPrincipal


class PaymentImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1, max_length=80)
    terminal_id: str = Field(min_length=1, max_length=80)
    authorization_code: str = Field(min_length=1, max_length=80)
    provider_reference: str = Field(min_length=1, max_length=120)
    sale_ref: str = Field(min_length=1, max_length=120)
    amount: int = Field(gt=0)
    occurred_at: str = Field(min_length=10, max_length=40)
    settlement_ref: str | None = Field(default=None, max_length=120)
    source: str = Field(pattern="^(pos_integration|provider_import|manual)$")


class SaleExpectationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sale_ref: str = Field(min_length=1, max_length=120)
    amount: int = Field(gt=0)
    emission_model: SiiEmissionModel
    fiscal_document_ref: str | None = Field(default=None, max_length=120)


class ReconcilePaymentsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sales: list[SaleExpectationRequest]


class PeopleSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: str = Field(pattern="^[0-9]{4}-(0[1-9]|1[0-2])$")
    worker_count: int = Field(ge=0)
    taxable_payroll: int = Field(ge=0)
    pension_obligations: int = Field(ge=0)
    single_tax: int = Field(ge=0)
    other_withholdings: int = Field(ge=0)
    source_version: str = Field(min_length=1, max_length=120)


def register_payment_routes(
    *, app: FastAPI, ledger: FolioLedger, authenticate: Callable[..., ApiPrincipal]
) -> None:
    @app.post("/v1/integrations/people/monthly-summaries", status_code=201)
    def import_people_summary(payload: PeopleSummaryRequest, principal=Depends(authenticate)):
        summary = PeopleMonthlySummary(**payload.model_dump())
        record = ledger.persist_people_summary(
            tenant_id=principal.tenant_id,
            period=summary.period,
            payload_sha256=summary.sha256,
            payload=payload.model_dump(),
        )
        return {**record.payload, "id": record.id, "version": record.version, "sha256": record.payload_sha256}

    @app.get("/v1/integrations/people/monthly-summaries/{year}/{month}")
    def latest_people_summary(year: int, month: int, principal=Depends(authenticate)):
        record = ledger.latest_people_summary(
            tenant_id=principal.tenant_id, period=f"{year:04d}-{month:02d}"
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Resumen Personas no encontrado")
        return {**record.payload, "id": record.id, "version": record.version, "sha256": record.payload_sha256}
    @app.post("/v1/payments/electronic", status_code=201)
    def import_payment(payload: PaymentImportRequest, principal=Depends(authenticate)):
        try:
            record = ledger.import_electronic_payment(
                tenant_id=principal.tenant_id, **payload.model_dump()
            )
        except FolioLedgerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return record.__dict__

    @app.post("/v1/payments/reconciliation/{year}/{month}")
    def reconcile(year: int, month: int, payload: ReconcilePaymentsRequest, principal=Depends(authenticate)):
        if not 1 <= month <= 12:
            raise HTTPException(status_code=422, detail="Mes inválido")
        period = f"{year:04d}-{month:02d}"
        records = ledger.list_electronic_payments(tenant_id=principal.tenant_id, period=period)
        payments = tuple(
            ElectronicPayment(
                record.provider, record.terminal_id, record.authorization_code,
                record.provider_reference, record.sale_ref, record.amount,
                record.occurred_at, record.settlement_ref
            ) for record in records
        )
        sales = tuple(SalePaymentExpectation(**sale.model_dump()) for sale in payload.sales)
        try:
            document_ids = {
                document.document_id
                for document in ledger.list_documents(tenant_id=principal.tenant_id, limit=200)
            }
            if any(
                sale.emission_model is SiiEmissionModel.ALWAYS_ISSUE
                and sale.fiscal_document_ref is not None
                and sale.fiscal_document_ref not in document_ids
                for sale in sales
            ):
                raise ValueError("El DTE indicado no existe en el ledger de este tenant")
            result = PaymentReconciliationService().reconcile(payments=payments, sales=sales)
            body = {
                "period": period,
                "ready": result.ready,
                "total": result.total,
                "items": [
                    {
                        "provider_reference": item.payment.provider_reference if item.payment else None,
                        "sale_ref": item.payment.sale_ref if item.payment else item.sale.sale_ref,
                        "amount": item.payment.amount if item.payment else item.sale.amount,
                        "state": item.state.value,
                        "detail": item.detail,
                        "fiscal_evidence": item.fiscal_evidence,
                    } for item in result.items
                ],
            }
            snapshot = ledger.persist_payment_reconciliation(
                tenant_id=principal.tenant_id, period=period, payload=body
            )
        except (ValueError, FolioLedgerError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {**body, "snapshot_id": snapshot.id, "version": snapshot.version, "sha256": snapshot.payload_sha256}

    @app.get("/v1/payments/reconciliation/{year}/{month}")
    def latest(year: int, month: int, principal=Depends(authenticate)):
        record = ledger.latest_payment_reconciliation(
            tenant_id=principal.tenant_id, period=f"{year:04d}-{month:02d}"
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Conciliación no encontrada")
        return {**record.payload, "snapshot_id": record.id, "version": record.version, "sha256": record.payload_sha256}
