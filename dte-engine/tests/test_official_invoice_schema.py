from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from importlib.resources import files

from completo_dte.domain import (
    DocumentType,
    EnvelopeAuthorization,
    EnvioDteBuilder,
    FiscalLine,
    InvoiceDteBuilder,
    PriceMode,
    TaxCategory,
    TedBuilder,
    XmlSchemaValidator,
    XmlSigner,
)
from factories import make_signing_credential, make_trusted_caf
from test_invoice_dte import make_invoice


def schema(name: str):
    return files("completo_dte").joinpath(
        "resources",
        "sii",
        "schema_dte_v10",
        name,
    )


def signed_invoice(document_type=DocumentType.FACTURA_AFECTA):
    invoice = make_invoice(document_type)
    invoice = replace(
        invoice,
        receiver=replace(
            invoice.receiver,
            city="SANTIAGO",
            email="facturas@example.test",
            phone="+56220000000",
        ),
    )
    caf = make_trusted_caf(document_type=int(document_type))
    credential = make_signing_credential()
    timestamp = datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc)
    ted = TedBuilder().build(invoice, caf, generated_at=timestamp)
    unsigned = InvoiceDteBuilder().build(invoice, ted, signed_at=timestamp)
    return XmlSigner().sign(unsigned, credential), credential, timestamp


def test_factura_and_envio_dte_validate_against_pinned_official_xsd() -> None:
    document, credential, timestamp = signed_invoice()
    XmlSchemaValidator(schema("DTE_v10.xsd")).validate(document.xml)

    envelope = EnvioDteBuilder().build(
        (document,),
        issuer_rut="12345678-5",
        sender_rut="12345678-5",
        authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
        signed_at=timestamp,
        credential=credential,
    )
    XmlSchemaValidator(schema("EnvioDTE_v10.xsd")).validate(envelope.xml)


def test_factura_exenta_34_validates_against_pinned_official_xsd() -> None:
    document, _credential, _timestamp = signed_invoice(DocumentType.FACTURA_EXENTA)
    XmlSchemaValidator(schema("DTE_v10.xsd")).validate(document.xml)


def test_mixed_factura_with_line_adjustments_validates_official_xsd() -> None:
    invoice = make_invoice(DocumentType.FACTURA_AFECTA)
    invoice = replace(
        invoice,
        lines=(
            FiscalLine(
                name="Servicio afecto",
                quantity=Decimal("2"),
                unit_price=Decimal("10000"),
                tax_category=TaxCategory.AFFECTED,
                price_mode=PriceMode.NET,
                discount_percent=Decimal("10"),
            ),
            FiscalLine(
                name="Servicio exento",
                quantity=Decimal("1"),
                unit_price=Decimal("5000"),
                tax_category=TaxCategory.EXEMPT,
                price_mode=PriceMode.NET,
                surcharge_amount=Decimal("500"),
            ),
        ),
    )
    caf = make_trusted_caf(document_type=33)
    credential = make_signing_credential()
    timestamp = datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc)
    ted = TedBuilder().build(invoice, caf, generated_at=timestamp)
    document = XmlSigner().sign(
        InvoiceDteBuilder().build(invoice, ted, signed_at=timestamp),
        credential,
    )

    XmlSchemaValidator(schema("DTE_v10.xsd")).validate(document.xml)
