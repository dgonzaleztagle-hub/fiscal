from datetime import date
from decimal import Decimal
import calendar
from completo_dte.domain import CommercialDocument,CommercialDocumentKind,CommercialLine
class RecurringBillingService:
 def __init__(self,ledger):self.ledger=ledger
 def generate_due_drafts(self,*,tenant_id,on_date:date,actor_ref="recurring-worker"):
  generated=[]
  for agreement in self.ledger.due_recurring_agreements(tenant_id=tenant_id,on_date=on_date.isoformat()):
   scheduled=date.fromisoformat(agreement.next_run_on);document=CommercialDocument(CommercialDocumentKind.SALES_ORDER,agreement.branch_id,agreement.counterparty_ref,agreement.counterparty_name,scheduled,None,"CLP",(CommercialLine(agreement.description,Decimal(1),Decimal(agreement.amount)),),"Borrador recurrente; requiere revisión antes de emitir DTE")
   record=self.ledger.create_commercial_document(tenant_id=tenant_id,idempotency_key=f"recurring:{agreement.id}:{scheduled.isoformat()}",document=document,actor_ref=actor_ref)
   year=scheduled.year+(1 if scheduled.month==12 else 0);month=1 if scheduled.month==12 else scheduled.month+1;day=min(agreement.day_of_month,calendar.monthrange(year,month)[1]);next_run=date(year,month,day)
   self.ledger.persist_recurring_execution(tenant_id=tenant_id,agreement_id=agreement.id,scheduled_on=scheduled.isoformat(),commercial_document_id=record.id,next_run_on=next_run.isoformat());generated.append(record)
  return tuple(generated)
