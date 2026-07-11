from importlib.resources import files

import pytest

from completo_dte.domain import ReceivedDocumentValidator
from completo_dte.infrastructure import FolioLedger, FolioLedgerError
from test_official_invoice_schema import signed_invoice


def received_document():
    signed, _credential, _timestamp = signed_invoice()
    schema = files("completo_dte").joinpath(
        "resources", "sii", "schema_dte_v10", "DTE_v10.xsd"
    )
    return ReceivedDocumentValidator(schema).validate(
        signed.xml, expected_receiver_rut="11111111-1"
    )


def test_received_import_is_idempotent_and_tenant_isolated(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "received.sqlite3")
    ledger.migrate()
    document = received_document()

    first = ledger.import_received_document(
        tenant_id="tenant-a", document=document, source="upload"
    )
    retry = ledger.import_received_document(
        tenant_id="tenant-a", document=document, source="email"
    )

    assert retry == first
    assert first.status == "pending"
    assert first.source == "upload"
    assert ledger.received_document_by_id(first.id, tenant_id="tenant-b") is None
    assert ledger.list_received_documents(tenant_id="tenant-b") == []
    assert ledger.list_received_documents(tenant_id="tenant-a") == [first]
    lines = ledger.received_document_lines(first.id, tenant_id="tenant-a")
    assert len(lines) == 1
    assert lines[0].name == "Servicio mensual"
    assert lines[0].amount == 18000
    assert ledger.received_document_lines(first.id, tenant_id="tenant-b") == []


def test_same_fiscal_identity_with_different_hash_is_rejected(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "received.sqlite3")
    ledger.migrate()
    document = received_document()
    ledger.import_received_document(
        tenant_id="tenant-a", document=document, source="upload"
    )

    changed = document.__class__(
        **{**document.__dict__, "xml_sha256": "f" * 64, "signed_xml": b"different"}
    )
    with pytest.raises(FolioLedgerError, match="XML diferente"):
        ledger.import_received_document(
            tenant_id="tenant-a", document=changed, source="upload"
        )


def test_received_payload_cannot_be_updated_or_deleted(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "received.sqlite3")
    ledger.migrate()
    record = ledger.import_received_document(
        tenant_id="tenant-a", document=received_document(), source="upload"
    )

    connection = ledger._connect()
    try:
        with pytest.raises(Exception, match="immutable"):
            connection.execute(
                "UPDATE received_fiscal_documents SET total = 1 WHERE id = ?",
                (record.id,),
            )
        with pytest.raises(Exception, match="cannot be deleted"):
            connection.execute(
                "DELETE FROM received_fiscal_documents WHERE id = ?", (record.id,)
            )
    finally:
        connection.close()
