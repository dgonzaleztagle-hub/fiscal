from datetime import datetime, timezone
from uuid import uuid4

from completo_sii_reader import ReaderResource, SiiSnapshot


def test_snapshot_hash_is_stable_for_equivalent_payloads() -> None:
    values = dict(
        run_id=uuid4(),
        tenant_id="tenant-demo",
        resource=ReaderResource.RCV,
        period="2026-07",
        captured_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    first = SiiSnapshot.create(payload={"total": 11900, "folio": 1}, **values)
    second = SiiSnapshot.create(payload={"folio": 1, "total": 11900}, **values)
    assert first.payload_sha256 == second.payload_sha256
