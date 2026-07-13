from decimal import Decimal
import pytest
from completo_dte.infrastructure import FolioLedger, FolioLedgerError


def test_inventory_is_append_only_idempotent_and_tenant_scoped(tmp_path):
    ledger=FolioLedger(tmp_path/"db.sqlite3"); ledger.migrate()
    product=ledger.create_inventory_product(tenant_id="a",sku="CAFE-1",name="Café",unit="kg")
    ledger.append_inventory_movement(tenant_id="a",product_id=product.id,branch_id="main",
        movement_type="purchase",quantity=Decimal("10"),source_ref="OC-1",reason="Recepción",
        actor_ref="owner",idempotency_key="move-1")
    retry=ledger.append_inventory_movement(tenant_id="a",product_id=product.id,branch_id="main",
        movement_type="purchase",quantity=Decimal("10"),source_ref="OC-1",reason="Recepción",
        actor_ref="owner",idempotency_key="move-1")
    ledger.append_inventory_movement(tenant_id="a",product_id=product.id,branch_id="main",
        movement_type="sale",quantity=Decimal("2.5"),source_ref="sale-1",reason="Venta",
        actor_ref="system",idempotency_key="move-2")
    assert retry.id
    assert ledger.inventory_balance(tenant_id="a",product_id=product.id,branch_id="main") == Decimal("7.5")
    assert ledger.inventory_balance(tenant_id="b",product_id=product.id,branch_id="main") == 0
    with pytest.raises(FolioLedgerError, match="otro movimiento"):
        ledger.append_inventory_movement(tenant_id="a",product_id=product.id,branch_id="main",
            movement_type="sale",quantity=Decimal("1"),source_ref="x",reason="x",
            actor_ref="owner",idempotency_key="move-1")
