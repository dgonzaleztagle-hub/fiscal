from completo_dte.domain import CommercialDocument,CommercialDocumentKind
from completo_dte.infrastructure import FolioLedgerError
class CommercialConversionService:
 def __init__(self,ledger):self.ledger=ledger
 def quote_to_sales_order(self,*,tenant_id,quote_id,actor_ref):
  source=self.ledger.get_commercial_document(tenant_id=tenant_id,record_id=quote_id)
  if source.status=="converted" and source.converted_document_id:return self.ledger.get_commercial_document(tenant_id=tenant_id,record_id=source.converted_document_id)
  if source.kind!="quote" or source.status!="accepted":raise FolioLedgerError("Sólo una cotización aceptada puede convertirse")
  target=self.ledger.create_commercial_document(tenant_id=tenant_id,idempotency_key=f"quote-to-order:{source.id}",actor_ref=actor_ref,document=CommercialDocument(CommercialDocumentKind.SALES_ORDER,source.branch_id,source.counterparty_ref,source.counterparty_name,__import__('datetime').date.fromisoformat(source.issued_on),None,source.currency,source.lines,f"Originada desde cotización {source.number}"))
  self.ledger.transition_commercial_document(tenant_id=tenant_id,record_id=source.id,target_status="converted",actor_ref=actor_ref,converted_document_id=target.id)
  return target
