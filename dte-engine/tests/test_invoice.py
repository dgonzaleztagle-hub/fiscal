from datetime import date
from decimal import Decimal

import pytest

from completo_dte.domain import (
    DocumentType,
    FiscalDocumentDraft,
    FiscalLine,
    Invoice,
    InvoiceError,
    Issuer,
    Party,
    PaymentTerms,
    PriceMode,
    TaxCategory,
)


def issuer() -> Issuer:
    return Issuer(
        rut="12345678-5",
        legal_name="SOFTWARE SINTETICO SPA",
        business_activity="DESARROLLO DE SOFTWARE",
        activity_code=620100,
        address="AVENIDA UNO 100",
        commune="SANTIAGO",
    )


def receiver() -> Party:
    return Party(
        rut="11111111-1",
        legal_name="CLIENTE SINTETICO SPA",
        business_activity="SERVICIOS EMPRESARIALES",
        address="CALLE DOS 200",
        commune="PROVIDENCIA",
    )


def line(
    name: str,
    quantity: str,
    unit_price: str,
    *,
    tax: TaxCategory = TaxCategory.AFFECTED,
    discount_percent: str = "0",
) -> FiscalLine:
    return FiscalLine(
        name=name,
        quantity=Decimal(quantity),
        unit_price=Decimal(unit_price),
        tax_category=tax,
        price_mode=PriceMode.NET,
        discount_percent=Decimal(discount_percent),
    )


def test_factura_33_matches_simple_reference_totals() -> None:
    invoice = Invoice(
        issuer=issuer(),
        receiver=receiver(),
        document_type=DocumentType.FACTURA_AFECTA,
        folio=1,
        issued_on=date(2026, 7, 10),
        lines=(line("Servicio", "450", "70"),),
    )

    assert invoice.net_total == 31_500
    assert invoice.exempt_total == 0
    assert invoice.vat_total == 5_985
    assert invoice.total == 37_485


def test_factura_34_and_mixed_factura_33_totals() -> None:
    exempt = Invoice(
        issuer=issuer(),
        receiver=receiver(),
        document_type=DocumentType.FACTURA_EXENTA,
        folio=2,
        issued_on=date(2026, 7, 10),
        lines=(line("Curso exento", "5", "25000", tax=TaxCategory.EXEMPT),),
    )
    mixed = Invoice(
        issuer=issuer(),
        receiver=receiver(),
        document_type=DocumentType.FACTURA_AFECTA,
        folio=3,
        issued_on=date(2026, 7, 10),
        lines=(
            line("Servicio afecto", "2", "1000", discount_percent="10"),
            line("Servicio exento", "1", "500", tax=TaxCategory.EXEMPT),
        ),
    )

    assert exempt.exempt_total == exempt.total == 125_000
    assert exempt.net_total == exempt.vat_total == 0
    assert mixed.net_total == 1_800
    assert mixed.vat_total == 342
    assert mixed.exempt_total == 500
    assert mixed.total == 2_642


def test_builds_invoice_from_canonical_draft() -> None:
    draft = FiscalDocumentDraft(
        tenant_id="tenant-a",
        branch_id="main",
        issuer_profile_id="issuer-a",
        document_type=DocumentType.FACTURA_AFECTA,
        issued_on=date(2026, 7, 10),
        receiver=receiver(),
        lines=(line("Servicio", "1", "10000"),),
        payment_terms=PaymentTerms.CREDIT,
        due_on=date(2026, 8, 10),
    )

    invoice = Invoice.from_draft(draft, issuer=issuer(), folio=9)

    assert invoice.folio == 9
    assert invoice.payment_terms == PaymentTerms.CREDIT
    assert invoice.due_on == date(2026, 8, 10)


def test_rejects_unsafe_or_incomplete_invoice_variants() -> None:
    gross_affected = FiscalLine(
        name="Precio bruto ambiguo",
        quantity=Decimal(1),
        unit_price=Decimal(1190),
        tax_category=TaxCategory.AFFECTED,
        price_mode=PriceMode.GROSS,
    )
    with pytest.raises(InvoiceError, match="precio neto"):
        Invoice(
            issuer=issuer(),
            receiver=receiver(),
            document_type=DocumentType.FACTURA_AFECTA,
            folio=1,
            issued_on=date(2026, 7, 10),
            lines=(gross_affected,),
        )

    incomplete_receiver = Party(rut="11111111-1", legal_name="CLIENTE")
    with pytest.raises(InvoiceError, match="giro del receptor"):
        Invoice(
            issuer=issuer(),
            receiver=incomplete_receiver,
            document_type=DocumentType.FACTURA_EXENTA,
            folio=1,
            issued_on=date(2026, 7, 10),
            lines=(line("Exento", "1", "100", tax=TaxCategory.EXEMPT),),
        )
