"""API de inventario por movimientos inmutables."""
from collections.abc import Callable
from decimal import Decimal
from fastapi import Depends,FastAPI,Header,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from completo_dte.infrastructure import FolioLedger,FolioLedgerError
from .security import ApiPrincipal

class ProductRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    sku:str=Field(min_length=1,max_length=80);name:str=Field(min_length=1,max_length=160);unit:str=Field(min_length=1,max_length=20)
class MovementRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    product_id:str=Field(min_length=1,max_length=120);branch_id:str=Field(min_length=1,max_length=120)
    movement_type:str=Field(pattern="^(purchase|sale|transfer_in|transfer_out|adjustment_in|adjustment_out|return_in|return_out)$")
    quantity:Decimal=Field(gt=0);source_ref:str=Field(min_length=1,max_length=120)
    reason:str=Field(min_length=1,max_length=300)
class MinimumRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    product_id:str;branch_id:str;minimum_quantity:Decimal=Field(ge=0)
class TransferRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    product_id:str;from_branch_id:str;to_branch_id:str;quantity:Decimal=Field(gt=0)

def register_inventory_routes(*,app:FastAPI,ledger:FolioLedger,authenticate:Callable[...,ApiPrincipal]):
    @app.get("/v1/inventory/products")
    def products(principal=Depends(authenticate)):
        return [item.__dict__ for item in ledger.list_inventory_products(tenant_id=principal.tenant_id)]
    @app.post("/v1/inventory/products",status_code=201)
    def product(payload:ProductRequest,principal=Depends(authenticate)):
        return _safe(lambda:ledger.create_inventory_product(tenant_id=principal.tenant_id,**payload.model_dump()))
    @app.post("/v1/inventory/movements",status_code=201)
    def movement(payload:MovementRequest,idempotency_key:str=Header(alias="Idempotency-Key",min_length=8,max_length=200),principal=Depends(authenticate)):
        return _safe(lambda:ledger.append_inventory_movement(tenant_id=principal.tenant_id,idempotency_key=idempotency_key,actor_ref=principal.actor_ref,**payload.model_dump()))
    @app.get("/v1/inventory/products/{product_id}/branches/{branch_id}/balance")
    def balance(product_id:str,branch_id:str,principal=Depends(authenticate)):
        return {"product_id":product_id,"branch_id":branch_id,"quantity":str(ledger.inventory_balance(tenant_id=principal.tenant_id,product_id=product_id,branch_id=branch_id))}
    @app.put("/v1/inventory/minimums")
    def minimum(payload:MinimumRequest,principal=Depends(authenticate)):
        ledger.set_inventory_minimum(tenant_id=principal.tenant_id,**payload.model_dump());return {"status":"saved"}
    @app.get("/v1/inventory/alerts/below-minimum")
    def alerts(principal=Depends(authenticate)):
        return ledger.inventory_below_minimum(tenant_id=principal.tenant_id)
    @app.post("/v1/inventory/transfers",status_code=201)
    def transfer(payload:TransferRequest,idempotency_key:str=Header(alias="Idempotency-Key",min_length=8),principal=Depends(authenticate)):
        try:return {"id":ledger.transfer_inventory(tenant_id=principal.tenant_id,actor_ref=principal.actor_ref,idempotency_key=idempotency_key,**payload.model_dump())}
        except FolioLedgerError as exc:raise HTTPException(status_code=409,detail=str(exc))from exc

def _safe(operation):
    try:return operation().__dict__
    except FolioLedgerError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc
