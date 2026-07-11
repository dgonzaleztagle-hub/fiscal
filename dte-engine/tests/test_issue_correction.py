from datetime import datetime, timezone
from dataclasses import replace
from decimal import Decimal

import pytest

from completo_dte.application import (
    AnnulDocumentCommand,
    CorrectTextCommand,
    IssueCorrectionCommand,
    IssueCorrectionService,
    IssueInvoiceService,
)
from completo_dte.infrastructure import FolioLedgerError
from factories import make_trusted_caf
from test_correction_dte import correction
from test_issue_invoice import setup_invoice


def setup_correction(tmp_path):
    ledger, invoice_caf, invoice_caf_id, credential, invoice_command = setup_invoice(tmp_path)
    invoice = IssueInvoiceService(
        ledger=ledger,
        resolve_caf=lambda requested: invoice_caf if requested == invoice_caf_id else None,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 10, 15, tzinfo=timezone.utc),
    ).issue(invoice_command)
    credit_caf = make_trusted_caf(document_type=61)
    credit_caf_id = ledger.import_caf("tenant-a", credit_caf)
    service = IssueCorrectionService(
        ledger=ledger,
        resolve_caf=lambda requested: credit_caf if requested == credit_caf_id else None,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 11, 15, tzinfo=timezone.utc),
    )
    note = correction()
    note = replace(note, reference=replace(note.reference, folio=invoice.folio))
    command = IssueCorrectionCommand(
        tenant_id="tenant-a",
        idempotency_key="credit-001",
        target_record_id=invoice.id,
        correction=note,
    )
    return ledger, service, command, invoice


def test_credit_note_is_linked_atomically_to_original(tmp_path) -> None:
    ledger, service, command, invoice = setup_correction(tmp_path)
    note = service.issue(command)
    retry = service.issue(command)

    assert note == retry
    assert note.document_type == 61
    relations = ledger.corrections_for(invoice.id, tenant_id="tenant-a")
    assert len(relations) == 1
    assert relations[0]["source_record_id"] == note.id
    assert relations[0]["correction_code"] == 3
    assert relations[0]["applied_amount"] == 1190


def test_credit_note_cannot_exceed_remaining_original_total(tmp_path) -> None:
    _ledger, service, command, _invoice = setup_correction(tmp_path)
    excessive_line = replace(
        command.correction.lines[0],
        unit_price=Decimal("20000"),
    )
    excessive = replace(
        command,
        idempotency_key="credit-excess",
        correction=replace(command.correction, lines=(excessive_line,)),
    )

    with pytest.raises(FolioLedgerError, match="saldo vigente"):
        service.issue(excessive)


def test_correction_rejects_crossed_receiver_before_reserving_folio(tmp_path) -> None:
    _ledger, service, command, _invoice = setup_correction(tmp_path)
    crossed = replace(
        command,
        correction=replace(
            command.correction,
            receiver=replace(command.correction.receiver, rut="76192083-9"),
        ),
    )

    with pytest.raises(ValueError, match="RUT receptor"):
        service.issue(crossed)


def test_annulment_is_derived_from_original_without_retyping_amounts(tmp_path) -> None:
    ledger, service, _command, invoice = setup_correction(tmp_path)

    annulment = service.annul(
        AnnulDocumentCommand(
            tenant_id="tenant-a",
            idempotency_key="annulment-001",
            target_record_id=invoice.id,
            issued_on=invoice_command_date(),
        )
    )

    assert annulment.document_type == 61
    assert b"<CodRef>1</CodRef>" in annulment.signed_xml
    assert b"<MntTotal>11900</MntTotal>" in annulment.signed_xml
    relation = ledger.corrections_for(invoice.id, tenant_id="tenant-a")[0]
    assert relation["applied_amount"] == 11900


def test_text_correction_changes_only_receiver_text_and_zero_amount(tmp_path) -> None:
    ledger, service, _command, invoice = setup_correction(tmp_path)

    note = service.correct_text(
        CorrectTextCommand(
            tenant_id="tenant-a",
            idempotency_key="text-fix-001",
            target_record_id=invoice.id,
            issued_on=invoice_command_date(),
            business_activity="GIRO CORREGIDO",
            address="DIRECCION CORREGIDA 123",
            commune="SANTIAGO",
        )
    )

    assert b"<CodRef>2</CodRef>" in note.signed_xml
    assert b"<MntTotal>0</MntTotal>" in note.signed_xml
    assert b"<GiroRecep>GIRO CORREGIDO</GiroRecep>" in note.signed_xml
    relation = ledger.corrections_for(invoice.id, tenant_id="tenant-a")[0]
    assert relation["applied_amount"] == 0


def invoice_command_date():
    from datetime import date

    return date(2026, 7, 11)
