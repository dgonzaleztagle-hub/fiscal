from datetime import date,timedelta
from decimal import Decimal
from completo_dte.application.commercial_conversion import CommercialConversionService
from completo_dte.domain import CommercialDocument,CommercialDocumentKind,CommercialLine
from completo_dte.infrastructure import FolioLedger
def test_accepted_quote_converts_to_one_sales_order(tmp_path):
 ledger=FolioLedger(tmp_path/"db");ledger.migrate();quote=CommercialDocument(CommercialDocumentKind.QUOTE,"main","c","Cliente",date.today(),date.today()+timedelta(days=10),"CLP",(CommercialLine("Servicio",Decimal(1),Decimal(1000)),));record=ledger.create_commercial_document(tenant_id="a",idempotency_key="q",document=quote,actor_ref="owner");ledger.transition_commercial_document(tenant_id="a",record_id=record.id,target_status="accepted",actor_ref="customer")
 service=CommercialConversionService(ledger);first=service.quote_to_sales_order(tenant_id="a",quote_id=record.id,actor_ref="owner");retry=service.quote_to_sales_order(tenant_id="a",quote_id=record.id,actor_ref="owner")
 assert first.id==retry.id and first.kind=="sales_order" and ledger.get_commercial_document(tenant_id="a",record_id=record.id).status=="converted"
