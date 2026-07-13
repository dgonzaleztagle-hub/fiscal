import pytest

from completo_dte.application import PeopleMonthlySummary
from completo_dte.infrastructure import FolioLedger


def test_people_summary_is_validated_hashed_versioned_and_tenant_scoped(tmp_path) -> None:
    summary = PeopleMonthlySummary("2026-07", 4, 3_200_000, 620_000, 45_000, 10_000, "people-v7")
    assert len(summary.sha256) == 64
    with pytest.raises(ValueError):
        PeopleMonthlySummary("2026-07", -1, 0, 0, 0, 0, "v1")
    ledger = FolioLedger(tmp_path / "db.sqlite3")
    ledger.migrate()
    record = ledger.persist_people_summary(
        tenant_id="tenant-a", period=summary.period,
        payload_sha256=summary.sha256, payload=summary.__dict__,
    )
    retry = ledger.persist_people_summary(
        tenant_id="tenant-a", period=summary.period,
        payload_sha256=summary.sha256, payload=summary.__dict__,
    )
    assert retry.id == record.id
    assert ledger.latest_people_summary(tenant_id="tenant-b", period="2026-07") is None
