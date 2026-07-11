from datetime import datetime, timezone
from io import BytesIO

from pypdf import PdfReader

from completo_dte.domain import InvoiceDteBuilder, TedBuilder
from completo_dte.presentation import InvoiceReceiptRenderer, ReceiptConfig
from factories import make_trusted_caf
from test_invoice_dte import make_invoice


def invoice_xml() -> bytes:
    invoice = make_invoice()
    timestamp = datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc)
    ted = TedBuilder().build(
        invoice,
        make_trusted_caf(document_type=33),
        generated_at=timestamp,
    )
    return InvoiceDteBuilder().build(invoice, ted, signed_at=timestamp).xml


def test_invoice_pdf_contains_issuer_receiver_totals_and_stamp() -> None:
    payload = InvoiceReceiptRenderer().render(
        invoice_xml(),
        ReceiptConfig(
            verification_url="https://documentos.completo.cl",
            resolution_number=80,
            resolution_year=2014,
        ),
    )
    reader = PdfReader(BytesIO(payload))
    page = reader.pages[0]
    text = page.extract_text()

    assert payload.startswith(b"%PDF-")
    assert "FACTURA ELECTRÓNICA" in text
    assert "SOFTWARE SINTETICO SPA" in text
    assert "CLIENTE SINTETICO SPA" in text
    assert "TOTAL" in text
    assert "$21.420" in text
    assert "Consulta: https://documentos.completo.cl" in text
    assert "/XObject" in page["/Resources"]
