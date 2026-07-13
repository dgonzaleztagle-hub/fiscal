import base64,binascii
from collections.abc import Callable
from fastapi import Depends,FastAPI,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from completo_dte.infrastructure import FolioLedger,FolioLedgerError
from .security import ApiPrincipal
class LinkRequest(BaseModel):
 model_config=ConfigDict(extra="forbid")
 bank_name:str=Field(min_length=1,max_length=80);account_type:str=Field(min_length=1,max_length=40);account_number_masked:str=Field(min_length=4,max_length=40);account_holder:str=Field(min_length=1,max_length=120);expires_at:str=Field(min_length=20,max_length=40)
class ProofRequest(BaseModel):
 model_config=ConfigDict(extra="forbid")
 file_name:str=Field(min_length=1,max_length=120);mime_type:str;content_base64:str=Field(max_length=7_000_000);declared_amount:int=Field(gt=0);payer_note:str|None=Field(default=None,max_length=500)
def register_collection_routes(*,app:FastAPI,ledger:FolioLedger,authenticate:Callable[...,ApiPrincipal]):
 @app.post("/v1/obligations/{obligation_id}/collection-link",status_code=201)
 def create(obligation_id:str,payload:LinkRequest,principal=Depends(authenticate)):
  try:return {"token":ledger.create_collection_link(tenant_id=principal.tenant_id,obligation_id=obligation_id,**payload.model_dump())}
  except FolioLedgerError as exc:raise HTTPException(status_code=409,detail=str(exc))from exc
 @app.get("/v1/public/collections/{token}")
 def inspect(token:str):
  try:return ledger.inspect_collection_link(token=token).__dict__
  except FolioLedgerError as exc:raise HTTPException(status_code=404,detail=str(exc))from exc
 @app.post("/v1/public/collections/{token}/proofs",status_code=201)
 def proof(token:str,payload:ProofRequest):
  try:
   content=base64.b64decode(payload.content_base64,validate=True);record_id=ledger.upload_payment_proof(token=token,content=content,**payload.model_dump(exclude={"content_base64"}));return {"id":record_id,"status":"pending_review"}
  except (FolioLedgerError,binascii.Error) as exc:raise HTTPException(status_code=422,detail=str(exc))from exc
