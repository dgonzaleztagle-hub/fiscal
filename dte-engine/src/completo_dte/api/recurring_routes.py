from collections.abc import Callable
from datetime import date
from fastapi import Depends,FastAPI,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from completo_dte.application.recurring_billing import RecurringBillingService
from completo_dte.infrastructure import FolioLedger
from .security import ApiPrincipal
class AgreementRequest(BaseModel):
 model_config=ConfigDict(extra="forbid")
 branch_id:str=Field(min_length=1,max_length=120);counterparty_ref:str=Field(min_length=1,max_length=120);counterparty_name:str=Field(min_length=1,max_length=120);description:str=Field(min_length=1,max_length=200);amount:int=Field(gt=0);day_of_month:int=Field(ge=1,le=28);next_run_on:date
def register_recurring_routes(*,app:FastAPI,ledger:FolioLedger,authenticate:Callable[...,ApiPrincipal]):
 @app.get("/v1/recurring-agreements")
 def listing(principal=Depends(authenticate)):
  return [item.__dict__ for item in ledger.list_recurring_agreements(tenant_id=principal.tenant_id)]
 @app.post("/v1/recurring-agreements",status_code=201)
 def create(payload:AgreementRequest,principal=Depends(authenticate)):
  try:return ledger.create_recurring_agreement(tenant_id=principal.tenant_id,**{**payload.model_dump(),"next_run_on":payload.next_run_on.isoformat()}).__dict__
  except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc))from exc
 @app.post("/v1/recurring-agreements/run")
 def run(on_date:date,principal=Depends(authenticate)):
  if not ({"system","owner"}&principal.roles):raise HTTPException(status_code=403,detail="Rol insuficiente")
  rows=RecurringBillingService(ledger).generate_due_drafts(tenant_id=principal.tenant_id,on_date=on_date,actor_ref=principal.actor_ref)
  return [{"id":row.id,"kind":row.kind,"number":row.number,"status":row.status,"total":row.total}for row in rows]
