from dataclasses import dataclass
from uuid import uuid4
from .ledger_codec import _now
@dataclass(frozen=True)
class RecurringAgreementRecord:
 id:str;tenant_id:str;branch_id:str;counterparty_ref:str;counterparty_name:str;description:str;amount:int;day_of_month:int;next_run_on:str;active:int;created_at:str
class RecurringLedgerMixin:
 def list_recurring_agreements(self,*,tenant_id):
  with self._connection() as c:rows=c.execute("SELECT * FROM recurring_agreements WHERE tenant_id=? ORDER BY next_run_on,id",(tenant_id,)).fetchall()
  return tuple(RecurringAgreementRecord(**dict(row)) for row in rows)
 def create_recurring_agreement(self,*,tenant_id,branch_id,counterparty_ref,counterparty_name,description,amount,day_of_month,next_run_on):
  if amount<=0 or not 1<=day_of_month<=28:raise ValueError("Acuerdo recurrente inválido")
  with self._transaction() as c:
   existing=c.execute("SELECT * FROM recurring_agreements WHERE tenant_id=? AND counterparty_ref=? AND description=?",(tenant_id,counterparty_ref,description)).fetchone()
   if existing:return RecurringAgreementRecord(**dict(existing))
   row=(str(uuid4()),tenant_id,branch_id,counterparty_ref,counterparty_name,description,amount,day_of_month,next_run_on,1,_now());c.execute("INSERT INTO recurring_agreements VALUES (?,?,?,?,?,?,?,?,?,?,?)",row);return RecurringAgreementRecord(*row)
 def due_recurring_agreements(self,*,tenant_id,on_date):
  with self._connection() as c:rows=c.execute("SELECT * FROM recurring_agreements WHERE tenant_id=? AND active=1 AND next_run_on<=? ORDER BY next_run_on,id",(tenant_id,on_date)).fetchall()
  return tuple(RecurringAgreementRecord(**dict(row)) for row in rows)
 def persist_recurring_execution(self,*,tenant_id,agreement_id,scheduled_on,commercial_document_id,next_run_on):
  with self._transaction() as c:
   existing=c.execute("SELECT commercial_document_id FROM recurring_executions WHERE tenant_id=? AND agreement_id=? AND scheduled_on=?",(tenant_id,agreement_id,scheduled_on)).fetchone()
   if existing:return existing["commercial_document_id"]
   c.execute("INSERT INTO recurring_executions VALUES (?,?,?,?,?,?)",(str(uuid4()),tenant_id,agreement_id,scheduled_on,commercial_document_id,_now()));c.execute("UPDATE recurring_agreements SET next_run_on=? WHERE id=? AND tenant_id=?",(next_run_on,agreement_id,tenant_id));return commercial_document_id
