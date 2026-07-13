"""API de documentos comerciales, separada de la emisión tributaria."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from completo_dte.domain import CommercialDocument, CommercialDocumentKind, CommercialLine
from completo_dte.infrastructure import FolioLedger, FolioLedgerError
from completo_dte.application.commercial_conversion import CommercialConversionService
from .security import ApiPrincipal


class CommercialLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=200)
    quantity: Decimal = Field(gt=0, decimal_places=6)
    unit_price: Decimal = Field(ge=0, decimal_places=4)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    product_ref: str | None = Field(default=None, max_length=120)


class CommercialCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: CommercialDocumentKind
    branch_id: str = Field(min_length=1, max_length=120)
    counterparty_ref: str = Field(min_length=1, max_length=120)
    counterparty_name: str = Field(min_length=1, max_length=120)
    issued_on: date
    valid_until: date | None = None
    currency: str = Field(default="CLP", min_length=3, max_length=3)
    notes: str = Field(default="", max_length=1000)
    lines: tuple[CommercialLineRequest, ...] = Field(min_length=1, max_length=200)


class CommercialTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(sent|accepted|rejected|cancelled|converted)$")
    converted_document_id: str | None = Field(default=None, max_length=120)

class PublicLinkRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    expires_at:str=Field(min_length=20,max_length=40)
class PublicDecisionRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    decision:str=Field(pattern="^(accepted|rejected)$")


def register_commercial_routes(*, app: FastAPI, ledger: FolioLedger,
                               authenticate: Callable[..., ApiPrincipal]) -> None:
    @app.post("/v1/commercial-documents", status_code=201)
    def create_commercial(payload: CommercialCreateRequest,
                          idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
                          principal=Depends(authenticate)):
        try:
            document = CommercialDocument(
                kind=payload.kind, branch_id=payload.branch_id,
                counterparty_ref=payload.counterparty_ref,
                counterparty_name=payload.counterparty_name,
                issued_on=payload.issued_on, valid_until=payload.valid_until,
                currency=payload.currency, notes=payload.notes,
                lines=tuple(CommercialLine(**line.model_dump()) for line in payload.lines),
            )
            return _response(ledger.create_commercial_document(
                tenant_id=principal.tenant_id, idempotency_key=idempotency_key,
                document=document, actor_ref=principal.actor_ref))
        except (ValueError, FolioLedgerError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/commercial-documents")
    def list_commercial(kind: str | None = Query(default=None),
                        status: str | None = Query(default=None),
                        principal=Depends(authenticate)):
        try:
            return [_response(item) for item in ledger.list_commercial_documents(
                tenant_id=principal.tenant_id, kind=kind, status=status)]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Filtro comercial inválido") from exc

    @app.post("/v1/commercial-documents/{record_id}/transitions")
    def transition(record_id: str, payload: CommercialTransitionRequest,
                   principal=Depends(authenticate)):
        try:
            return _response(ledger.transition_commercial_document(
                tenant_id=principal.tenant_id, record_id=record_id,
                target_status=payload.status, actor_ref=principal.actor_ref,
                converted_document_id=payload.converted_document_id))
        except (ValueError, FolioLedgerError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/commercial-documents/{record_id}/convert-to-sales-order",status_code=201)
    def convert_to_order(record_id:str,principal=Depends(authenticate)):
        try:return _response(CommercialConversionService(ledger).quote_to_sales_order(tenant_id=principal.tenant_id,quote_id=record_id,actor_ref=principal.actor_ref))
        except FolioLedgerError as exc:raise HTTPException(status_code=409,detail=str(exc))from exc

    @app.post("/v1/commercial-documents/{record_id}/public-link",status_code=201)
    def public_link(record_id:str,payload:PublicLinkRequest,principal=Depends(authenticate)):
        try:return {"token":ledger.create_commercial_public_link(tenant_id=principal.tenant_id,record_id=record_id,expires_at=payload.expires_at)}
        except FolioLedgerError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc

    @app.get("/v1/public/commercial/{token}")
    def inspect_public(token:str):
        try:
            record=ledger.inspect_commercial_public_link(token=token)
            return {"kind":record.kind,"number":record.number,"counterparty_name":record.counterparty_name,"issued_on":record.issued_on,"valid_until":record.valid_until,"currency":record.currency,"total":record.total,"lines":[{"description":line.description,"quantity":str(line.quantity),"subtotal":line.subtotal} for line in record.lines]}
        except FolioLedgerError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc

    @app.post("/v1/public/commercial/{token}/decision")
    def decide_public(token:str,payload:PublicDecisionRequest):
        try:return _response(ledger.decide_commercial_public_link(token=token,decision=payload.decision))
        except FolioLedgerError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


def _response(record) -> dict:
    return {**record.__dict__, "lines": [
        {"description": line.description, "quantity": str(line.quantity),
         "unit_price": str(line.unit_price), "discount_percent": str(line.discount_percent),
         "product_ref": line.product_ref, "subtotal": line.subtotal}
        for line in record.lines]}
