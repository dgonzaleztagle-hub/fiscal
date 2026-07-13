from datetime import date
from completo_dte.application.recurring_billing import RecurringBillingService
from completo_dte.infrastructure import FolioLedger
def test_recurring_worker_generates_one_reviewable_draft_per_period(tmp_path):
 ledger=FolioLedger(tmp_path/"db");ledger.migrate();ledger.create_recurring_agreement(tenant_id="a",branch_id="main",counterparty_ref="c",counterparty_name="Cliente",description="Servicio mensual",amount=100000,day_of_month=15,next_run_on="2026-07-15")
 service=RecurringBillingService(ledger);first=service.generate_due_drafts(tenant_id="a",on_date=date(2026,7,15));retry=service.generate_due_drafts(tenant_id="a",on_date=date(2026,7,15))
 assert len(first)==1 and first[0].status=="draft" and retry==()
 assert ledger.due_recurring_agreements(tenant_id="a",on_date="2026-08-14")==()
