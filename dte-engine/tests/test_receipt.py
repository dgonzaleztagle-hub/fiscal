from datetime import datetime, timezone

import pytest
from pypdf import PdfReader
import zxingcpp

from completo_dte.domain import DteBuilder
from completo_dte.presentation import BoletaReceiptRenderer, ReceiptConfig, ReceiptError
from completo_dte.presentation.receipt import _extract_original_ted, _pdf417
from test_dte import make_document


def _dte() -> bytes:
    _caf, boleta, ted = make_document()
    return DteBuilder().build(
        boleta,
        ted,
        signed_at=datetime(2026, 7, 8, 15, 31, tzinfo=timezone.utc),
    ).xml


def test_receipt_contains_fiscal_data_and_pdf417_image() -> None:
    payload = BoletaReceiptRenderer().render(
        _dte(),
        ReceiptConfig(
            verification_url="https://boletas.completo.cl",
            resolution_number=80,
            resolution_year=2014,
        ),
    )
    reader = PdfReader(__import__("io").BytesIO(payload))
    page = reader.pages[0]
    text = page.extract_text()

    assert payload.startswith(b"%PDF-")
    assert "BOLETA ELECTRÓNICA" in text
    assert "RESTAURANTE SINTETICO SPA" in text
    assert "Verifique documento: https://boletas.completo.cl" in text
    assert "/XObject" in page["/Resources"]
    assert float(page.mediabox.width) >= 57 * 72 / 25.4


def test_receipt_rejects_insecure_query_url() -> None:
    with pytest.raises(ReceiptError, match="HTTPS"):
        ReceiptConfig(
            verification_url="http://boletas.example.test",
            resolution_number=80,
            resolution_year=2014,
        )


def test_pdf417_decodes_back_to_exact_original_ted() -> None:
    xml = _dte()
    expected = _extract_original_ted(xml)
    result = zxingcpp.read_barcode(_pdf417(expected))

    assert result is not None
    assert result.bytes == expected
