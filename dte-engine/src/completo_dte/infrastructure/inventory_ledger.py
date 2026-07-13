"""Inventario por movimientos: ningún saldo se edita directamente."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from .ledger_codec import _now, _required_token
from .records import FolioLedgerError


@dataclass(frozen=True)
class InventoryProductRecord:
    id: str; tenant_id: str; sku: str; name: str; unit: str; active: int; created_at: str


@dataclass(frozen=True)
class InventoryMovementRecord:
    id: str; tenant_id: str; product_id: str; branch_id: str; movement_type: str
    quantity: str; source_ref: str; reason: str; actor_ref: str
    idempotency_key: str; occurred_at: str


class InventoryLedgerMixin:
    def set_inventory_minimum(self,*,tenant_id,product_id,branch_id,minimum_quantity:Decimal):
        if minimum_quantity<0:raise FolioLedgerError("El mínimo no puede ser negativo")
        with self._transaction() as c:c.execute("INSERT INTO inventory_minimums VALUES (?,?,?,?,?) ON CONFLICT(tenant_id,product_id,branch_id) DO UPDATE SET minimum_quantity=excluded.minimum_quantity,updated_at=excluded.updated_at",(tenant_id,product_id,branch_id,str(minimum_quantity),_now()))

    def inventory_below_minimum(self,*,tenant_id):
        with self._connection() as c:rows=c.execute("SELECT product_id,branch_id,minimum_quantity FROM inventory_minimums WHERE tenant_id=?",(tenant_id,)).fetchall()
        return tuple({"product_id":row["product_id"],"branch_id":row["branch_id"],"minimum":str(row["minimum_quantity"]),"balance":str(self.inventory_balance(tenant_id=tenant_id,product_id=row["product_id"],branch_id=row["branch_id"]))}for row in rows if self.inventory_balance(tenant_id=tenant_id,product_id=row["product_id"],branch_id=row["branch_id"])<Decimal(row["minimum_quantity"]))

    def transfer_inventory(self,*,tenant_id,product_id,from_branch_id,to_branch_id,quantity:Decimal,actor_ref,idempotency_key):
        if from_branch_id==to_branch_id or quantity<=0:raise FolioLedgerError("Traslado inválido")
        if self.inventory_balance(tenant_id=tenant_id,product_id=product_id,branch_id=from_branch_id)<quantity:raise FolioLedgerError("Stock insuficiente para traslado")
        with self._transaction() as c:
            existing=c.execute("SELECT id FROM inventory_transfers WHERE tenant_id=? AND idempotency_key=?",(tenant_id,idempotency_key)).fetchone()
            if existing:return existing["id"]
            transfer_id=str(uuid4());now=_now();c.execute("INSERT INTO inventory_transfers VALUES (?,?,?,?,?,?,?,?,?)",(transfer_id,tenant_id,product_id,from_branch_id,to_branch_id,str(quantity),actor_ref,idempotency_key,now))
            for branch,kind in ((from_branch_id,"transfer_out"),(to_branch_id,"transfer_in")):
                c.execute("INSERT INTO inventory_movements VALUES (?,?,?,?,?,?,?,?,?,?,?)",(str(uuid4()),tenant_id,product_id,branch,kind,str(quantity),transfer_id,"Traslado pareado",actor_ref,f"transfer:{transfer_id}:{kind}",now))
            return transfer_id
    def list_inventory_products(self, *, tenant_id: str) -> tuple[InventoryProductRecord,...]:
        with self._connection() as connection:
            rows=connection.execute("SELECT * FROM inventory_products WHERE tenant_id=? AND active=1 ORDER BY name,sku",(tenant_id,)).fetchall()
        return tuple(InventoryProductRecord(**dict(row)) for row in rows)

    def create_inventory_product(self, *, tenant_id: str, sku: str, name: str,
                                 unit: str) -> InventoryProductRecord:
        for value, label in ((tenant_id,"tenant_id"),(sku,"sku"),(name,"name"),(unit,"unit")):
            _required_token(value, label)
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM inventory_products WHERE tenant_id=? AND sku=?", (tenant_id, sku)
            ).fetchone()
            if existing:
                if existing["name"] != name or existing["unit"] != unit:
                    raise FolioLedgerError("El SKU ya existe con datos diferentes")
                return InventoryProductRecord(**dict(existing))
            record = (str(uuid4()), tenant_id, sku, name, unit, 1, _now())
            connection.execute("INSERT INTO inventory_products VALUES (?,?,?,?,?,?,?)", record)
            return InventoryProductRecord(*record)

    def append_inventory_movement(self, *, tenant_id: str, product_id: str,
                                  branch_id: str, movement_type: str,
                                  quantity: Decimal, source_ref: str, reason: str,
                                  actor_ref: str, idempotency_key: str) -> InventoryMovementRecord:
        allowed = {"purchase","sale","transfer_in","transfer_out","adjustment_in","adjustment_out","return_in","return_out"}
        if movement_type not in allowed or quantity <= 0:
            raise FolioLedgerError("Movimiento de inventario inválido")
        with self._transaction() as connection:
            product = connection.execute(
                "SELECT id FROM inventory_products WHERE id=? AND tenant_id=? AND active=1", (product_id, tenant_id)
            ).fetchone()
            if not product:
                raise FolioLedgerError("Producto no encontrado en este tenant")
            existing = connection.execute(
                "SELECT * FROM inventory_movements WHERE tenant_id=? AND idempotency_key=?",
                (tenant_id, idempotency_key),
            ).fetchone()
            if existing:
                same = (existing["product_id"]==product_id and existing["branch_id"]==branch_id
                        and existing["movement_type"]==movement_type and existing["quantity"]==str(quantity))
                if not same: raise FolioLedgerError("La idempotency key de inventario ya tiene otro movimiento")
                return InventoryMovementRecord(**dict(existing))
            record = (str(uuid4()), tenant_id, product_id, branch_id, movement_type,
                      str(quantity), source_ref, reason, actor_ref, idempotency_key, _now())
            connection.execute("INSERT INTO inventory_movements VALUES (?,?,?,?,?,?,?,?,?,?,?)", record)
            return InventoryMovementRecord(*record)

    def inventory_balance(self, *, tenant_id: str, product_id: str,
                          branch_id: str) -> Decimal:
        positive = {"purchase","transfer_in","adjustment_in","return_in"}
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT movement_type,quantity FROM inventory_movements WHERE tenant_id=? AND product_id=? AND branch_id=?",
                (tenant_id, product_id, branch_id),
            ).fetchall()
        return sum((Decimal(row["quantity"]) * (1 if row["movement_type"] in positive else -1) for row in rows), Decimal("0"))
