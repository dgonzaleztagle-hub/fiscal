from datetime import datetime,timedelta,timezone
import pytest
from completo_dte.infrastructure import FolioLedger,FolioLedgerError
def test_collection_portal_never_marks_payment_without_review(tmp_path):
 ledger=FolioLedger(tmp_path/"db");ledger.migrate();obligation=ledger.create_obligation(tenant_id="a",direction="receivable",counterparty_ref="c",counterparty_name="Cliente",source_ref="F33-1",branch_id="main",amount=100000,due_on="2026-08-01")
 token=ledger.create_collection_link(tenant_id="a",obligation_id=obligation.id,bank_name="Banco",account_type="Corriente",account_number_masked="****1234",account_holder="Empresa",expires_at=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat())
 portal=ledger.inspect_collection_link(token=token);assert portal.outstanding==100000
 proof_id=ledger.upload_payment_proof(token=token,file_name="pago.png",mime_type="image/png",content=b"synthetic-image",declared_amount=50000,payer_note="Transferido")
 assert proof_id and ledger.list_obligations(tenant_id="a")[0].status=="open"
 with pytest.raises(FolioLedgerError,match="Monto declarado"):ledger.upload_payment_proof(token=token,file_name="x.png",mime_type="image/png",content=b"other",declared_amount=200000,payer_note=None)
