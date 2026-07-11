from datetime import date, datetime, timezone

from lxml import etree
import pytest

from completo_dte.domain import (
    DailyFolio,
    DailySummaryError,
    DailySummaryBuilder,
    EnvelopeAuthorization,
    XmlSigner,
)
from completo_dte.domain.xml_signature import SII
from factories import make_signing_credential


def test_builds_signed_daily_summary_with_used_and_voided_ranges() -> None:
    credential = make_signing_credential()
    summary = DailySummaryBuilder().build(
        (
            DailyFolio(39, 1, date(2026, 7, 9), 1000, 190, 0, 1190),
            DailyFolio(39, 2, date(2026, 7, 9), 2000, 380, 100, 2480),
            DailyFolio(39, 3, date(2026, 7, 9), voided=True),
            DailyFolio(39, 5, date(2026, 7, 9), 500, 95, 0, 595),
        ),
        issuer_rut="12345678-5",
        sender_rut="12345678-5",
        authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
        sequence=1,
        signed_at=datetime(2026, 7, 9, 15, 30, tzinfo=timezone.utc),
        credential=credential,
        document_id="RCOF_20260709",
    )

    root = etree.fromstring(summary.xml)
    ns = {"sii": SII}
    assert root.findtext(".//sii:MntNeto", namespaces=ns) == "3500"
    assert root.findtext(".//sii:MntIva", namespaces=ns) == "665"
    assert root.findtext(".//sii:MntExento", namespaces=ns) == "100"
    assert root.findtext(".//sii:MntTotal", namespaces=ns) == "4265"
    assert root.findtext(".//sii:FoliosEmitidos", namespaces=ns) == "3"
    assert root.findtext(".//sii:FoliosAnulados", namespaces=ns) == "1"
    assert root.findtext(".//sii:FoliosUtilizados", namespaces=ns) == "4"
    used = [
        (
            int(node.findtext("sii:Inicial", namespaces=ns)),
            int(node.findtext("sii:Final", namespaces=ns)),
        )
        for node in root.findall(".//sii:RangoUtilizados", ns)
    ]
    assert used == [(1, 3), (5, 5)]
    assert XmlSigner().verify_raw(
        summary.xml,
        target_tag=f"{{{SII}}}DocumentoConsumoFolios",
        target_id=summary.document_id,
        expected_certificate=credential.certificate,
    )


def test_rejects_folios_from_multiple_days_in_daily_summary() -> None:
    credential = make_signing_credential()
    with pytest.raises(DailySummaryError, match="misma fecha"):
        DailySummaryBuilder().build(
            (
                DailyFolio(39, 1, date(2026, 7, 8), 1000, 190, 0, 1190),
                DailyFolio(39, 2, date(2026, 7, 9), 1000, 190, 0, 1190),
            ),
            issuer_rut="12345678-5",
            sender_rut="12345678-5",
            authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
            sequence=1,
            signed_at=datetime(2026, 7, 9, 15, 30, tzinfo=timezone.utc),
            credential=credential,
        )
