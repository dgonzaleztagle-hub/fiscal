from datetime import date
from decimal import Decimal

import pytest

from completo_dte.domain import CommercialDocument, CommercialDocumentKind, CommercialLine
from completo_dte.infrastructure import FolioLedger, FolioLedgerError


def quote(name="Cliente Uno"):
    return CommercialDocument(
        CommercialDocumentKind.QUOTE, "main", "client-1", name,
        date(2026, 7, 13), date(2026, 7, 28), "CLP",
        (CommercialLine("Servicio mensual", Decimal("2"), Decimal("10000"), Decimal("10")),),
    )


def test_commercial_document_is_tenant_scoped_and_idempotent(tmp_path):
    ledger = FolioLedger(tmp_path / "db.sqlite3"); ledger.migrate()
    first = ledger.create_commercial_document(
        tenant_id="tenant-a", idempotency_key="quote-0001", document=quote(), actor_ref="owner")
    retry = ledger.create_commercial_document(
        tenant_id="tenant-a", idempotency_key="quote-0001", document=quote(), actor_ref="owner")
    assert first.id == retry.id
    assert first.number == 1 and first.total == 18000 and first.status == "draft"
    assert ledger.list_commercial_documents(tenant_id="tenant-b") == ()
    with pytest.raises(FolioLedgerError, match="otros datos"):
        ledger.create_commercial_document(
            tenant_id="tenant-a", idempotency_key="quote-0001", document=quote("Otro"), actor_ref="owner")


def test_commercial_state_machine_requires_explicit_conversion(tmp_path):
    ledger = FolioLedger(tmp_path / "db.sqlite3"); ledger.migrate()
    record = ledger.create_commercial_document(
        tenant_id="tenant-a", idempotency_key="quote-0002", document=quote(), actor_ref="owner")
    sent = ledger.transition_commercial_document(
        tenant_id="tenant-a", record_id=record.id, target_status="sent", actor_ref="owner")
    accepted = ledger.transition_commercial_document(
        tenant_id="tenant-a", record_id=record.id, target_status="accepted", actor_ref="customer")
    assert sent.status == "sent" and accepted.status == "accepted"
    with pytest.raises(FolioLedgerError, match="documento resultante"):
        ledger.transition_commercial_document(
            tenant_id="tenant-a", record_id=record.id, target_status="converted", actor_ref="owner")
    converted = ledger.transition_commercial_document(
        tenant_id="tenant-a", record_id=record.id, target_status="converted",
        actor_ref="owner", converted_document_id="fiscal-doc-1")
    assert converted.converted_document_id == "fiscal-doc-1"
