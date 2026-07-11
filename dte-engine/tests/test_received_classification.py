import sqlite3

import pytest

from completo_dte.domain import PurchaseDestination, PurchaseLineAllocation
from completo_dte.infrastructure import FolioLedger, FolioLedgerError
from test_received_ledger import received_document


def test_classification_is_versioned_not_overwritten_and_tenant_isolated(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "classification.sqlite3")
    ledger.migrate()
    received = ledger.import_received_document(
        tenant_id="tenant-a", document=received_document(), source="upload"
    )
    first = ledger.classify_received_document(
        tenant_id="tenant-a",
        received_document_id=received.id,
        provider_id="provider-1",
        destination="expense",
        category_code="software",
        notes="Clasificación inicial",
        classified_by="user-1",
    )
    corrected = ledger.classify_received_document(
        tenant_id="tenant-a",
        received_document_id=received.id,
        provider_id="provider-1",
        destination="fixed_asset",
        category_code="equipment",
        notes="Reclasificado con respaldo",
        classified_by="user-2",
    )

    assert first.version == 1
    assert corrected.version == 2
    assert ledger.latest_received_classification(
        received.id, tenant_id="tenant-a"
    ) == corrected
    assert ledger.latest_received_classification(
        received.id, tenant_id="tenant-b"
    ) is None


def test_classification_history_cannot_be_mutated_or_deleted(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "classification.sqlite3")
    ledger.migrate()
    received = ledger.import_received_document(
        tenant_id="tenant-a", document=received_document(), source="upload"
    )
    record = ledger.classify_received_document(
        tenant_id="tenant-a",
        received_document_id=received.id,
        provider_id=None,
        destination="unassigned",
        category_code=None,
        notes=None,
        classified_by="user-1",
    )
    connection = ledger._connect()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE received_document_classifications SET destination='expense' WHERE id=?",
                (record.id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            connection.execute(
                "DELETE FROM received_document_classifications WHERE id=?", (record.id,)
            )
    finally:
        connection.close()


def test_cross_tenant_classification_is_rejected(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "classification.sqlite3")
    ledger.migrate()
    received = ledger.import_received_document(
        tenant_id="tenant-a", document=received_document(), source="upload"
    )
    with pytest.raises(FolioLedgerError, match="no encontrado"):
        ledger.classify_received_document(
            tenant_id="tenant-b",
            received_document_id=received.id,
            provider_id=None,
            destination="expense",
            category_code=None,
            notes=None,
            classified_by="intruder",
        )


def test_mixed_classification_assigns_real_xml_lines_to_control_plane(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "classification.sqlite3")
    ledger.migrate()
    received = ledger.import_received_document(
        tenant_id="tenant-a", document=received_document(), source="upload"
    )
    classification = ledger.classify_received_document(
        tenant_id="tenant-a",
        received_document_id=received.id,
        provider_id="provider-1",
        destination="mixed",
        category_code=None,
        notes="Asignación por detalle",
        classified_by="user-1",
    )
    allocations = ledger.allocate_received_lines(
        tenant_id="tenant-a",
        classification_id=classification.id,
        allocations=(
            PurchaseLineAllocation(1, PurchaseDestination.INVENTORY, "product-1"),
        ),
    )
    assert allocations[0].destination == "inventory"
    assert allocations[0].control_plane_ref == "product-1"
    with pytest.raises(FolioLedgerError, match="ya fueron asignadas"):
        ledger.allocate_received_lines(
            tenant_id="tenant-a",
            classification_id=classification.id,
            allocations=(PurchaseLineAllocation(1, PurchaseDestination.EXPENSE),),
        )
