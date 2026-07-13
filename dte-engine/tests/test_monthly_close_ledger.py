import pytest

from completo_dte.infrastructure import FolioLedger, FolioLedgerError


def persist(ledger: FolioLedger, calculation: str = "b"):
    return ledger.persist_monthly_close(
        tenant_id="tenant-a",
        period="2026-07",
        formula_version="plus-baseline-2026-07-v1",
        source_sha256="a" * 64,
        calculation_sha256=calculation * 64,
        payload={"total_payable": 157_492},
    )


def test_monthly_close_versions_are_idempotent_and_tenant_scoped(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "fiscal.sqlite3")
    ledger.migrate()
    first = persist(ledger)
    retry = persist(ledger)
    second = persist(ledger, "c")

    assert retry.id == first.id
    assert first.version == 1
    assert second.version == 2
    assert [record.version for record in ledger.list_monthly_closes(tenant_id="tenant-a", period="2026-07")] == [2, 1]
    assert ledger.list_monthly_closes(tenant_id="tenant-b", period="2026-07") == ()


def test_monthly_close_review_requires_order_and_cannot_cross_tenants(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "fiscal.sqlite3")
    ledger.migrate()
    snapshot = persist(ledger)
    with pytest.raises(FolioLedgerError, match="tenant"):
        ledger.review_monthly_close(
            tenant_id="tenant-b", snapshot_id=snapshot.id, actor_ref="user-1", action="opened"
        )
    with pytest.raises(FolioLedgerError, match="transición"):
        ledger.review_monthly_close(
            tenant_id="tenant-a", snapshot_id=snapshot.id, actor_ref="user-1", action="frozen"
        )
    for action in ("opened", "marked_ready", "reviewed", "frozen"):
        result = ledger.review_monthly_close(
            tenant_id="tenant-a",
            snapshot_id=snapshot.id,
            actor_ref="user-1",
            action=action,
            reason="Revisión sintética",
        )
        assert result.action == action
    with pytest.raises(FolioLedgerError, match="transición"):
        ledger.review_monthly_close(
            tenant_id="tenant-a", snapshot_id=snapshot.id, actor_ref="user-1", action="opened"
        )
