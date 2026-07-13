from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
import pytest
from completo_dte.domain import CommercialDocument,CommercialDocumentKind,CommercialLine
from completo_dte.infrastructure import FolioLedger,FolioLedgerError

def test_quote_public_link_is_single_use_and_changes_state(tmp_path):
 ledger=FolioLedger(tmp_path/"db");ledger.migrate();quote=CommercialDocument(CommercialDocumentKind.QUOTE,"main","c","Cliente",date.today(),date.today()+timedelta(days=15),"CLP",(CommercialLine("Servicio",Decimal(1),Decimal(1000)),))
 record=ledger.create_commercial_document(tenant_id="a",idempotency_key="quote-public",document=quote,actor_ref="owner")
 token=ledger.create_commercial_public_link(tenant_id="a",record_id=record.id,expires_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat())
 assert ledger.inspect_commercial_public_link(token=token).status=="sent"
 assert ledger.decide_commercial_public_link(token=token,decision="accepted").status=="accepted"
 with pytest.raises(FolioLedgerError,match="utilizado"):ledger.inspect_commercial_public_link(token=token)
