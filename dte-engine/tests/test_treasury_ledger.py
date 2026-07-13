import pytest
from completo_dte.infrastructure import FolioLedger,FolioLedgerError

def test_partial_payments_projection_and_tenant_isolation(tmp_path):
    ledger=FolioLedger(tmp_path/"db");ledger.migrate()
    recv=ledger.create_obligation(tenant_id="a",direction="receivable",counterparty_ref="c",counterparty_name="Cliente",source_ref="F33-1",branch_id="main",amount=100000,due_on="2026-07-20")
    ledger.create_obligation(tenant_id="a",direction="payable",counterparty_ref="p",counterparty_name="Proveedor",source_ref="P33-1",branch_id="main",amount=40000,due_on="2026-07-21")
    paid=ledger.register_obligation_payment(tenant_id="a",obligation_id=recv.id,amount=30000,paid_on="2026-07-14",method="transfer",evidence_ref="cartola-1",actor_ref="owner",idempotency_key="pay-1")
    assert paid.status=="partial" and paid.outstanding==70000
    assert ledger.projected_cash(tenant_id="a",from_on="2026-07-15",to_on="2026-07-31")["net"]==30000
    assert ledger.projected_cash(tenant_id="b",from_on="2026-07-01",to_on="2026-07-31")["net"]==0
    with pytest.raises(FolioLedgerError,match="supera"):
        ledger.register_obligation_payment(tenant_id="a",obligation_id=recv.id,amount=80000,paid_on="2026-07-14",method="transfer",evidence_ref=None,actor_ref="owner",idempotency_key="pay-2")

def test_approval_can_only_be_decided_once(tmp_path):
    ledger=FolioLedger(tmp_path/"db");ledger.migrate()
    approval=ledger.request_approval(tenant_id="a",operation_type="purchase_order",operation_ref="OC-1",amount=1200000,requested_by="buyer",required_role="owner")
    decided=ledger.decide_approval(tenant_id="a",approval_id=approval.id,decision="approved",decided_by="owner",reason="Compra necesaria",actor_roles=("owner",))
    assert decided.status=="approved"
    with pytest.raises(FolioLedgerError,match="disponible"):
        ledger.decide_approval(tenant_id="a",approval_id=approval.id,decision="rejected",decided_by="owner",reason="Cambio",actor_roles=("owner",))

def test_approval_rejects_actor_without_required_role(tmp_path):
    ledger=FolioLedger(tmp_path/"db");ledger.migrate()
    approval=ledger.request_approval(tenant_id="a",operation_type="payment",operation_ref="P-1",amount=800000,requested_by="buyer",required_role="owner")
    with pytest.raises(FolioLedgerError,match="rol requerido"):
        ledger.decide_approval(tenant_id="a",approval_id=approval.id,decision="approved",decided_by="waiter",reason="Intento",actor_roles=("operator",))
