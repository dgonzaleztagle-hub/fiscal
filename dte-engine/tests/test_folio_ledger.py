from concurrent.futures import ThreadPoolExecutor

import pytest

from completo_dte.infrastructure import (
    CafRangeExhausted,
    FolioLedger,
    FolioLedgerError,
    LeaseState,
)
from factories import make_trusted_caf

HASH_A = "a" * 64


def make_ledger(tmp_path, *, folio_to: int = 100) -> FolioLedger:
    ledger = FolioLedger(tmp_path / "folio-ledger.sqlite3")
    ledger.migrate()
    ledger.import_caf("tenant-a", make_trusted_caf(folio_to=folio_to))
    return ledger


def test_reservation_is_idempotent(tmp_path) -> None:
    ledger = make_ledger(tmp_path)
    first = ledger.reserve(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
        document_type=39,
        idempotency_key="sale-123",
        request_sha256=HASH_A,
    )
    retry = ledger.reserve(
        tenant_id="tenant-a",
        taxpayer_rut="12.345.678-5",
        document_type=39,
        idempotency_key="sale-123",
        request_sha256=HASH_A,
    )
    assert retry == first
    assert retry.folio == 1
    assert len(ledger.events(first.id)) == 1


def test_concurrent_reservations_never_duplicate_a_folio(tmp_path) -> None:
    ledger = make_ledger(tmp_path, folio_to=40)

    def reserve(index: int):
        return ledger.reserve(
            tenant_id="tenant-a",
            taxpayer_rut="12345678-5",
            document_type=39,
            idempotency_key=f"sale-{index}",
            request_sha256=f"{index:064x}",
        )

    with ThreadPoolExecutor(max_workers=12) as executor:
        leases = tuple(executor.map(reserve, range(40)))

    folios = {lease.folio for lease in leases}
    assert folios == set(range(1, 41))
    assert len({lease.id for lease in leases}) == 40
    with pytest.raises(CafRangeExhausted):
        reserve(41)


def test_concurrent_retries_return_one_lease(tmp_path) -> None:
    ledger = make_ledger(tmp_path)

    def retry(_index: int):
        return ledger.reserve(
            tenant_id="tenant-a",
            taxpayer_rut="12345678-5",
            document_type=39,
            idempotency_key="same-sale",
            request_sha256=HASH_A,
        )

    with ThreadPoolExecutor(max_workers=10) as executor:
        leases = tuple(executor.map(retry, range(20)))

    assert len({lease.id for lease in leases}) == 1
    assert {lease.folio for lease in leases} == {1}


def test_consume_is_idempotent_and_append_only(tmp_path) -> None:
    ledger = make_ledger(tmp_path)
    reserved = ledger.reserve(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
        document_type=39,
        idempotency_key="sale-1",
        request_sha256=HASH_A,
    )
    consumed = ledger.consume(reserved.id, "F1T39")
    retry = ledger.consume(reserved.id, "F1T39")

    assert consumed.status == LeaseState.CONSUMED
    assert retry == consumed
    assert [event["event_type"] for event in ledger.events(reserved.id)] == [
        "reserved",
        "consumed",
    ]
    with pytest.raises(FolioLedgerError, match="consumed"):
        ledger.void(reserved.id, "No reutilizar")


def test_voided_folio_is_never_reused(tmp_path) -> None:
    ledger = make_ledger(tmp_path)
    first = ledger.reserve(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
        document_type=39,
        idempotency_key="sale-1",
        request_sha256=HASH_A,
    )
    voided = ledger.void(first.id, "Venta cancelada antes de emitir")
    second = ledger.reserve(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
        document_type=39,
        idempotency_key="sale-2",
        request_sha256="b" * 64,
    )
    assert voided.status == LeaseState.VOIDED
    assert (first.folio, second.folio) == (1, 2)


def test_rejects_overlapping_active_caf_ranges(tmp_path) -> None:
    ledger = make_ledger(tmp_path, folio_to=100)
    with pytest.raises(FolioLedgerError, match="superpone"):
        ledger.import_caf(
            "tenant-a",
            make_trusted_caf(folio_from=50, folio_to=150),
        )


def test_read_operations_close_sqlite_connections(tmp_path) -> None:
    database = tmp_path / "folio-ledger.sqlite3"
    ledger = make_ledger(tmp_path)
    lease = ledger.reserve(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
        document_type=39,
        idempotency_key="sale-close",
        request_sha256=HASH_A,
    )
    assert ledger.document_by_lease(lease.id) is None
    assert ledger.document_by_id("missing", tenant_id="tenant-a") is None
    ledger.events(lease.id)

    renamed = tmp_path / "renamed.sqlite3"
    database.replace(renamed)
    assert renamed.exists()


def test_migrations_are_versioned_and_idempotent(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "migrations.sqlite3")
    ledger.migrate()
    ledger.migrate()
