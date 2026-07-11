from datetime import date, datetime, timezone
from decimal import Decimal
from xml.etree import ElementTree

from completo_dte.domain import (
    DocumentType,
    FiscalLine,
    Invoice,
    InvoiceDteBuilder,
    Issuer,
    Party,
    PaymentTerms,
    PriceMode,
    TaxCategory,
    TedBuilder,
    XmlSigner,
)
from factories import make_signing_credential, make_trusted_caf


def make_invoice(document_type: DocumentType = DocumentType.FACTURA_AFECTA) -> Invoice:
    tax = (
        TaxCategory.AFFECTED
        if document_type == DocumentType.FACTURA_AFECTA
        else TaxCategory.EXEMPT
    )
    return Invoice(
        issuer=Issuer(
            rut="12345678-5",
            legal_name="SOFTWARE SINTETICO SPA",
            business_activity="DESARROLLO DE SOFTWARE",
            activity_code=620100,
            address="AVENIDA UNO 100",
            commune="SANTIAGO",
        ),
        receiver=Party(
            rut="11111111-1",
            legal_name="CLIENTE SINTETICO SPA",
            business_activity="SERVICIOS EMPRESARIALES",
            address="CALLE DOS 200",
            commune="PROVIDENCIA",
            city="SANTIAGO",
            email="facturas@example.test",
            phone="+56220000000",
        ),
        document_type=document_type,
        folio=7,
        issued_on=date(2026, 7, 10),
        lines=(
            FiscalLine(
                name="Servicio mensual",
                quantity=Decimal("2"),
                unit_price=Decimal("10000"),
                tax_category=tax,
                price_mode=PriceMode.NET,
                discount_percent=Decimal("10"),
            ),
        ),
        payment_terms=PaymentTerms.CREDIT,
        due_on=date(2026, 8, 10),
    )


def test_builds_and_signs_factura_33() -> None:
    invoice = make_invoice()
    caf = make_trusted_caf(document_type=33)
    timestamp = datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc)
    ted = TedBuilder().build(invoice, caf, generated_at=timestamp)
    unsigned = InvoiceDteBuilder().build(invoice, ted, signed_at=timestamp)
    credential = make_signing_credential()
    signed = XmlSigner().sign(unsigned, credential)

    namespace = {"sii": "http://www.sii.cl/SiiDte"}
    root = ElementTree.fromstring(unsigned.xml)
    assert root.findtext(".//sii:TipoDTE", namespaces=namespace) == "33"
    assert root.findtext(".//sii:RznSoc", namespaces=namespace) == "SOFTWARE SINTETICO SPA"
    assert root.findtext(".//sii:GiroRecep", namespaces=namespace) == "SERVICIOS EMPRESARIALES"
    assert root.findtext(".//sii:Contacto", namespaces=namespace) == "+56220000000"
    assert root.findtext(".//sii:CorreoRecep", namespaces=namespace) == "facturas@example.test"
    assert root.findtext(".//sii:FmaPago", namespaces=namespace) == "2"
    assert root.findtext(".//sii:FchVenc", namespaces=namespace) == "2026-08-10"
    assert root.findtext(".//sii:MntNeto", namespaces=namespace) == "18000"
    assert root.findtext(".//sii:IVA", namespaces=namespace) == "3420"
    assert root.findtext(".//sii:MntTotal", namespaces=namespace) == "21420"
    assert root.findtext(".//sii:DescuentoPct", namespaces=namespace) == "10"
    assert root.findtext(".//sii:DescuentoMonto", namespaces=namespace) == "2000"
    assert ted.verify(caf)
    assert XmlSigner().verify_with_certificate(signed, credential.certificate)


def test_builds_factura_exenta_34() -> None:
    invoice = make_invoice(DocumentType.FACTURA_EXENTA)
    caf = make_trusted_caf(document_type=34)
    timestamp = datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc)
    ted = TedBuilder().build(invoice, caf, generated_at=timestamp)
    unsigned = InvoiceDteBuilder().build(invoice, ted, signed_at=timestamp)

    namespace = {"sii": "http://www.sii.cl/SiiDte"}
    root = ElementTree.fromstring(unsigned.xml)
    assert root.findtext(".//sii:TipoDTE", namespaces=namespace) == "34"
    assert root.find(".//sii:MntNeto", namespace) is None
    assert root.find(".//sii:IVA", namespace) is None
    assert root.findtext(".//sii:MntExe", namespaces=namespace) == "18000"
    assert root.findtext(".//sii:MntTotal", namespaces=namespace) == "18000"
    assert root.find(".//sii:IndExe", namespace) is None
