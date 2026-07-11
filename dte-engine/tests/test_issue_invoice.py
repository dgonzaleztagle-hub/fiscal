from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from completo_dte.application import IssueInvoiceCommand, IssueInvoiceService
from completo_dte.domain import (
    DocumentType,
    FiscalDocumentDraft,
    FiscalLine,
    Issuer,
    Party,
    PaymentTerms,
    PriceMode,
    SignedDte,
    TaxCategory,
    XmlSigner,
)
from completo_dte.infrastructure import FolioLedger, FolioLedgerError
from factories import make_signing_credential, make_trusted_caf


def setup_invoice(tmp_path):
    ledger = FolioLedger(tmp_path / "invoices.sqlite3")
    ledger.migrate()
    caf = make_trusted_caf(document_type=33)
    caf_id = ledger.import_caf("tenant-a", caf)
    credential = make_signing_credential()
    issuer = Issuer(
        rut="12345678-5",
        legal_name="SOFTWARE SINTETICO SPA",
        business_activity="DESARROLLO DE SOFTWARE",
        activity_code=620100,
        address="AVENIDA UNO 100",
        commune="SANTIAGO",
    )
    draft = FiscalDocumentDraft(
        tenant_id="tenant-a",
        branch_id="main",
        issuer_profile_id="issuer-a",
        document_type=DocumentType.FACTURA_AFECTA,
        issued_on=date(2026, 7, 10),
        receiver=Party(
            rut="11111111-1",
            legal_name="CLIENTE SINTETICO SPA",
            business_activity="SERVICIOS EMPRESARIALES",
            address="CALLE DOS 200",
            commune="PROVIDENCIA",
        ),
        lines=(
            FiscalLine(
                name="Servicio mensual",
                quantity=Decimal(1),
                unit_price=Decimal(10000),
                tax_category=TaxCategory.AFFECTED,
                price_mode=PriceMode.NET,
            ),
        ),
        payment_terms=PaymentTerms.CREDIT,
        due_on=date(2026, 8, 10),
    )
    command = IssueInvoiceCommand(
        idempotency_key="invoice-001",
        issuer=issuer,
        draft=draft,
    )
    return ledger, caf, caf_id, credential, command


def test_issues_idempotent_signed_invoice_and_consumes_folio(tmp_path) -> None:
    ledger, caf, caf_id, credential, command = setup_invoice(tmp_path)
    calls = 0

    def clock():
        nonlocal calls
        calls += 1
        return datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc) + timedelta(hours=calls)

    service = IssueInvoiceService(
        ledger=ledger,
        resolve_caf=lambda requested: caf if requested == caf_id else None,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=clock,
    )
    first = service.issue(command)
    retry = service.issue(command)

    assert first == retry
    assert first.document_id == "F1T33"
    assert first.document_type == 33
    assert calls == 1
    assert XmlSigner().verify_with_certificate(
        SignedDte(xml=first.signed_xml, document_id=first.document_id),
        credential.certificate,
    )


def test_invoice_idempotency_rejects_changed_payload(tmp_path) -> None:
    ledger, caf, _caf_id, credential, command = setup_invoice(tmp_path)
    service = IssueInvoiceService(
        ledger=ledger,
        resolve_caf=lambda _requested: caf,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc),
    )
    service.issue(command)
    changed_line = FiscalLine(
        **{**command.draft.lines[0].__dict__, "unit_price": Decimal(99999)}
    )
    changed = IssueInvoiceCommand(
        idempotency_key=command.idempotency_key,
        issuer=command.issuer,
        draft=FiscalDocumentDraft(
            **{**command.draft.__dict__, "lines": (changed_line,)}
        ),
    )

    with pytest.raises(FolioLedgerError, match="payload diferente"):
        service.issue(changed)
