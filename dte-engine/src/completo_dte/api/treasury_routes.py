"""API tenant-first de cobranza, pagos, proyección y aprobaciones."""
from collections.abc import Callable
from fastapi import Depends,FastAPI,Header,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from completo_dte.infrastructure import FolioLedger,FolioLedgerError
from .security import ApiPrincipal

class ObligationRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    direction:str=Field(pattern="^(receivable|payable)$")
    counterparty_ref:str=Field(min_length=1,max_length=120)
    counterparty_name:str=Field(min_length=1,max_length=120)
    source_ref:str=Field(min_length=1,max_length=120)
    branch_id:str=Field(min_length=1,max_length=120)
    amount:int=Field(gt=0); due_on:str=Field(pattern="^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
class PaymentRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    amount:int=Field(gt=0);paid_on:str=Field(pattern="^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    method:str=Field(min_length=1,max_length=40);evidence_ref:str|None=None
class ApprovalRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    operation_type:str=Field(min_length=1,max_length=80);operation_ref:str=Field(min_length=1,max_length=120)
    amount:int=Field(ge=0);required_role:str=Field(min_length=1,max_length=80)
class DecisionRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    decision:str=Field(pattern="^(approved|rejected)$");reason:str=Field(min_length=1,max_length=500)

def register_treasury_routes(*,app:FastAPI,ledger:FolioLedger,authenticate:Callable[...,ApiPrincipal]):
    @app.post("/v1/obligations",status_code=201)
    def create(payload:ObligationRequest,principal=Depends(authenticate)):
        return _safe(lambda:ledger.create_obligation(tenant_id=principal.tenant_id,**payload.model_dump()))
    @app.get("/v1/obligations")
    def listing(direction:str|None=None,principal=Depends(authenticate)):
        return [item.__dict__ for item in ledger.list_obligations(tenant_id=principal.tenant_id,direction=direction)]
    @app.post("/v1/obligations/{obligation_id}/payments",status_code=201)
    def pay(obligation_id:str,payload:PaymentRequest,idempotency_key:str=Header(alias="Idempotency-Key",min_length=8),principal=Depends(authenticate)):
        return _safe(lambda:ledger.register_obligation_payment(tenant_id=principal.tenant_id,obligation_id=obligation_id,idempotency_key=idempotency_key,actor_ref=principal.actor_ref,**payload.model_dump()))
    @app.get("/v1/cash-flow/projection")
    def projection(from_on:str,to_on:str,principal=Depends(authenticate)):
        return ledger.projected_cash(tenant_id=principal.tenant_id,from_on=from_on,to_on=to_on)
    @app.post("/v1/approvals",status_code=201)
    def request(payload:ApprovalRequest,principal=Depends(authenticate)):
        return ledger.request_approval(tenant_id=principal.tenant_id,requested_by=principal.actor_ref,**payload.model_dump()).__dict__
    @app.get("/v1/approvals")
    def approvals(status:str|None=None,principal=Depends(authenticate)):
        return [item.__dict__ for item in ledger.list_approvals(tenant_id=principal.tenant_id,status=status)]
    @app.post("/v1/approvals/{approval_id}/decision")
    def decide(approval_id:str,payload:DecisionRequest,principal=Depends(authenticate)):
        return _safe(lambda:ledger.decide_approval(tenant_id=principal.tenant_id,approval_id=approval_id,decided_by=principal.actor_ref,actor_roles=principal.roles,**payload.model_dump()))

def _safe(operation):
    try:return operation().__dict__
    except FolioLedgerError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc
