"""Cuentas por cobrar/pagar, pagos parciales y aprobaciones auditables."""
from dataclasses import dataclass
from datetime import date
from uuid import uuid4
from .ledger_codec import _now, _required_token
from .records import FolioLedgerError

@dataclass(frozen=True)
class ObligationRecord:
    id:str; tenant_id:str; direction:str; counterparty_ref:str; counterparty_name:str
    source_ref:str; branch_id:str; amount:int; due_on:str; status:str; created_at:str
    paid:int=0; outstanding:int=0

@dataclass(frozen=True)
class ApprovalRecord:
    id:str; tenant_id:str; operation_type:str; operation_ref:str; amount:int
    requested_by:str; required_role:str; status:str; decided_by:str|None
    reason:str|None; created_at:str; decided_at:str|None

class TreasuryLedgerMixin:
    def create_obligation(self, *, tenant_id, direction, counterparty_ref,
                          counterparty_name, source_ref, branch_id, amount, due_on):
        if direction not in {"receivable","payable"} or amount<=0:
            raise FolioLedgerError("Obligación financiera inválida")
        for value,label in ((tenant_id,"tenant_id"),(source_ref,"source_ref"),(counterparty_ref,"counterparty_ref")):
            _required_token(value,label)
        with self._transaction() as c:
            existing=c.execute("SELECT * FROM financial_obligations WHERE tenant_id=? AND direction=? AND source_ref=?",(tenant_id,direction,source_ref)).fetchone()
            if existing:
                if existing["amount"]!=amount or existing["due_on"]!=due_on: raise FolioLedgerError("La obligación ya existe con datos diferentes")
                return self._obligation(c,existing)
            row=(str(uuid4()),tenant_id,direction,counterparty_ref,counterparty_name,source_ref,branch_id,amount,due_on,"open",_now())
            c.execute("INSERT INTO financial_obligations VALUES (?,?,?,?,?,?,?,?,?,?,?)",row)
            return self._obligation(c,c.execute("SELECT * FROM financial_obligations WHERE id=?",(row[0],)).fetchone())

    def register_obligation_payment(self, *, tenant_id, obligation_id, amount,
                                    paid_on, method, evidence_ref, actor_ref, idempotency_key):
        if amount<=0: raise FolioLedgerError("El pago debe ser positivo")
        with self._transaction() as c:
            obligation=c.execute("SELECT * FROM financial_obligations WHERE id=? AND tenant_id=?",(obligation_id,tenant_id)).fetchone()
            if not obligation or obligation["status"] in {"paid","cancelled"}: raise FolioLedgerError("Obligación no disponible")
            existing=c.execute("SELECT * FROM obligation_payments WHERE tenant_id=? AND idempotency_key=?",(tenant_id,idempotency_key)).fetchone()
            if existing:
                if existing["obligation_id"]!=obligation_id or existing["amount"]!=amount: raise FolioLedgerError("La idempotency key de pago ya fue utilizada")
                return self._obligation(c,obligation)
            paid=c.execute("SELECT COALESCE(SUM(amount),0) value FROM obligation_payments WHERE obligation_id=?",(obligation_id,)).fetchone()["value"]
            if paid+amount>obligation["amount"]: raise FolioLedgerError("El pago supera el saldo pendiente")
            c.execute("INSERT INTO obligation_payments VALUES (?,?,?,?,?,?,?,?,?,?)",(str(uuid4()),tenant_id,obligation_id,amount,paid_on,method,evidence_ref,actor_ref,idempotency_key,_now()))
            status="paid" if paid+amount==obligation["amount"] else "partial"
            c.execute("UPDATE financial_obligations SET status=? WHERE id=?",(status,obligation_id))
            return self._obligation(c,c.execute("SELECT * FROM financial_obligations WHERE id=?",(obligation_id,)).fetchone())

    def list_obligations(self, *, tenant_id, direction=None):
        sql="SELECT * FROM financial_obligations WHERE tenant_id=?"; params=[tenant_id]
        if direction: sql+=" AND direction=?"; params.append(direction)
        sql+=" ORDER BY due_on,id"
        with self._connection() as c: return tuple(self._obligation(c,row) for row in c.execute(sql,params).fetchall())

    def projected_cash(self, *, tenant_id, from_on, to_on):
        rows=self.list_obligations(tenant_id=tenant_id)
        included=[r for r in rows if from_on<=r.due_on<=to_on and r.status not in {"paid","cancelled"}]
        incoming=sum(r.outstanding for r in included if r.direction=="receivable")
        outgoing=sum(r.outstanding for r in included if r.direction=="payable")
        return {"from_on":from_on,"to_on":to_on,"incoming":incoming,"outgoing":outgoing,"net":incoming-outgoing}

    def request_approval(self, *, tenant_id, operation_type, operation_ref, amount, requested_by, required_role):
        with self._transaction() as c:
            existing=c.execute("SELECT * FROM approval_requests WHERE tenant_id=? AND operation_type=? AND operation_ref=?",(tenant_id,operation_type,operation_ref)).fetchone()
            if existing:return ApprovalRecord(**dict(existing))
            row=(str(uuid4()),tenant_id,operation_type,operation_ref,amount,requested_by,required_role,"pending",None,None,_now(),None)
            c.execute("INSERT INTO approval_requests VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",row)
            return ApprovalRecord(*row)

    def list_approvals(self, *, tenant_id, status=None):
        sql="SELECT * FROM approval_requests WHERE tenant_id=?";params=[tenant_id]
        if status:sql+=" AND status=?";params.append(status)
        sql+=" ORDER BY created_at DESC"
        with self._connection() as c:return tuple(ApprovalRecord(**dict(row)) for row in c.execute(sql,params).fetchall())

    def decide_approval(self, *, tenant_id, approval_id, decision, decided_by, reason, actor_roles=("system",)):
        if decision not in {"approved","rejected"}: raise FolioLedgerError("Decisión inválida")
        with self._transaction() as c:
            row=c.execute("SELECT * FROM approval_requests WHERE id=? AND tenant_id=?",(approval_id,tenant_id)).fetchone()
            if not row or row["status"]!="pending": raise FolioLedgerError("Aprobación no disponible")
            if "system" not in actor_roles and row["required_role"] not in actor_roles:
                raise FolioLedgerError("El actor no posee el rol requerido para aprobar")
            c.execute("UPDATE approval_requests SET status=?,decided_by=?,reason=?,decided_at=? WHERE id=?",(decision,decided_by,reason,_now(),approval_id))
            return ApprovalRecord(**dict(c.execute("SELECT * FROM approval_requests WHERE id=?",(approval_id,)).fetchone()))

    def _obligation(self,c,row):
        paid=c.execute("SELECT COALESCE(SUM(amount),0) value FROM obligation_payments WHERE obligation_id=?",(row["id"],)).fetchone()["value"]
        return ObligationRecord(**dict(row),paid=paid,outstanding=row["amount"]-paid)
