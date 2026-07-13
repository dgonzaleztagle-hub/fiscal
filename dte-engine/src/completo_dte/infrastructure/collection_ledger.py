import hashlib,secrets
from dataclasses import dataclass
from datetime import datetime,timezone
from uuid import uuid4
from .ledger_codec import _now
from .records import FolioLedgerError
@dataclass(frozen=True)
class CollectionPortalRecord:
 link_id:str;obligation_id:str;counterparty_name:str;source_ref:str;amount:int;paid:int;outstanding:int;due_on:str;bank_name:str;account_type:str;account_number_masked:str;account_holder:str;expires_at:str
class CollectionLedgerMixin:
 def create_collection_link(self,*,tenant_id,obligation_id,bank_name,account_type,account_number_masked,account_holder,expires_at):
  token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest()
  with self._transaction() as c:
   obligation=c.execute("SELECT * FROM financial_obligations WHERE id=? AND tenant_id=? AND direction='receivable' AND status IN('open','partial')",(obligation_id,tenant_id)).fetchone()
   if not obligation:raise FolioLedgerError("Cuenta por cobrar no disponible")
   c.execute("INSERT INTO collection_links VALUES (?,?,?,?,?,?,?,?,?,?,?)",(str(uuid4()),tenant_id,obligation_id,digest,bank_name,account_type,account_number_masked,account_holder,expires_at,None,_now()))
  return token
 def inspect_collection_link(self,*,token):
  digest=hashlib.sha256(token.encode()).hexdigest()
  with self._connection() as c:
   link=c.execute("SELECT * FROM collection_links WHERE token_sha256=? AND revoked_at IS NULL",(digest,)).fetchone()
   if not link or datetime.fromisoformat(link["expires_at"]).astimezone(timezone.utc)<=datetime.now(timezone.utc):raise FolioLedgerError("Enlace de cobro inválido o vencido")
   obligation=c.execute("SELECT * FROM financial_obligations WHERE id=?",(link["obligation_id"],)).fetchone();paid=c.execute("SELECT COALESCE(SUM(amount),0) value FROM obligation_payments WHERE obligation_id=?",(obligation["id"],)).fetchone()["value"]
   return CollectionPortalRecord(link["id"],obligation["id"],obligation["counterparty_name"],obligation["source_ref"],obligation["amount"],paid,obligation["amount"]-paid,obligation["due_on"],link["bank_name"],link["account_type"],link["account_number_masked"],link["account_holder"],link["expires_at"])
 def upload_payment_proof(self,*,token,file_name,mime_type,content,declared_amount,payer_note):
  if len(content)>5_000_000 or mime_type not in {"application/pdf","image/jpeg","image/png"}:raise FolioLedgerError("Comprobante inválido o demasiado grande")
  portal=self.inspect_collection_link(token=token)
  if declared_amount<=0 or declared_amount>portal.outstanding:raise FolioLedgerError("Monto declarado inválido")
  digest=hashlib.sha256(content).hexdigest()
  with self._transaction() as c:
   existing=c.execute("SELECT id FROM payment_proofs WHERE collection_link_id=? AND content_sha256=?",(portal.link_id,digest)).fetchone()
   if existing:return existing["id"]
   record_id=str(uuid4());c.execute("INSERT INTO payment_proofs VALUES (?,?,?,?,?,?,?,?,?,?)",(record_id,c.execute("SELECT tenant_id FROM collection_links WHERE id=?",(portal.link_id,)).fetchone()["tenant_id"],portal.link_id,file_name,mime_type,digest,content,declared_amount,payer_note,_now()));return record_id
