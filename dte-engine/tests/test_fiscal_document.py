from datetime import date
from decimal import Decimal

import pytest

from completo_dte.domain import (
    CorrectionCode,
    DispatchReason,
    DocumentType,
    FiscalDocumentDraft,
    FiscalDocumentError,
    FiscalLine,
    FiscalReference,
    Party,
    PaymentTerms,
    PriceMode,
    TaxCategory,
)


RECEIVER = Party(
    rut="76.192.083-9",
    legal_name="CLIENTE SINTETICO SPA",
    business_activity="SERVICIOS",
    address="CALLE DOS 456",
    commune="SANTIAGO",
)


def line(*, tax_category=TaxCategory.AFFECTED) -> FiscalLine:
    return FiscalLine(
        name="Servicio mensual",
        quantity=Decimal("1"),
        unit_price=Decimal("10000"),
        tax_category=tax_category,
        price_mode=PriceMode.NET,
    )


def draft(document_type: DocumentType, **overrides) -> FiscalDocumentDraft:
    data = {
        "tenant_id": "tenant-demo",
        "branch_id": "casa-matriz",
        "issuer_profile_id": "issuer-demo",
        "document_type": document_type,
        "issued_on": date(2026, 7, 9),
        "lines": (line(),),
        "receiver": RECEIVER,
    }
    data.update(overrides)
    return FiscalDocumentDraft(**data)


@pytest.mark.parametrize(
    "document_type",
    (
        DocumentType.FACTURA_AFECTA,
        DocumentType.FACTURA_EXENTA,
        DocumentType.BOLETA_AFECTA,
        DocumentType.BOLETA_EXENTA,
        DocumentType.GUIA_DESPACHO,
        DocumentType.NOTA_DEBITO,
        DocumentType.NOTA_CREDITO,
    ),
)
def test_canonical_contract_knows_every_v1_document_type(document_type) -> None:
    assert int(document_type) in {33, 34, 39, 41, 52, 56, 61}


def test_invoice_requires_identified_receiver() -> None:
    with pytest.raises(FiscalDocumentError, match="receptor"):
        draft(DocumentType.FACTURA_AFECTA, receiver=None)


def test_exempt_document_rejects_affected_line() -> None:
    with pytest.raises(FiscalDocumentError, match="sólo admite"):
        draft(DocumentType.FACTURA_EXENTA)


def test_note_requires_original_document_and_correction_code() -> None:
    with pytest.raises(FiscalDocumentError, match="Una nota"):
        draft(DocumentType.NOTA_CREDITO)

    note = draft(
        DocumentType.NOTA_CREDITO,
        references=(
            FiscalReference(
                line_number=1,
                document_type="33",
                folio="123",
                issued_on=date(2026, 7, 1),
                correction_code=CorrectionCode.VOID,
                reason="ANULA DOCUMENTO",
            ),
        ),
    )
    assert note.references[0].correction_code is CorrectionCode.VOID


def test_guide_requires_dispatch_reason() -> None:
    with pytest.raises(FiscalDocumentError, match="motivo"):
        draft(DocumentType.GUIA_DESPACHO)
    guide = draft(
        DocumentType.GUIA_DESPACHO,
        dispatch_reason=DispatchReason.INTERNAL_TRANSFER,
    )
    assert guide.dispatch_reason is DispatchReason.INTERNAL_TRANSFER


def test_credit_requires_due_date() -> None:
    with pytest.raises(FiscalDocumentError, match="vencimiento"):
        draft(DocumentType.FACTURA_AFECTA, payment_terms=PaymentTerms.CREDIT)


def test_line_rejects_ambiguous_discount() -> None:
    with pytest.raises(FiscalDocumentError, match="no ambos"):
        FiscalLine(
            name="Producto",
            quantity=Decimal("1"),
            unit_price=Decimal("1000"),
            tax_category=TaxCategory.AFFECTED,
            price_mode=PriceMode.NET,
            discount_percent=Decimal("10"),
            discount_amount=Decimal("100"),
        )
