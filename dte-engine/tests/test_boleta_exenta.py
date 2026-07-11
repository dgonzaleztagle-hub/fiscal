from datetime import date, datetime, timezone
from decimal import Decimal

from lxml import etree
import pytest

from completo_dte.domain import (
    BoletaError,
    BoletaExenta,
    BoletaLine,
    DteBuilder,
    EnvelopeAuthorization,
    EnvioBoletaBuilder,
    Issuer,
    TedBuilder,
    XmlSigner,
)
from completo_dte.domain.xml_signature import SII
from factories import make_signing_credential, make_trusted_caf
from test_dte import make_document


def make_exempt_boleta(*, folio: int = 11) -> BoletaExenta:
    return BoletaExenta(
        issuer=Issuer(
            rut="12345678-5",
            legal_name="RESTAURANTE SINTETICO SPA",
            business_activity="RESTAURANTES",
            activity_code=561000,
        ),
        folio=folio,
        issued_on=date(2026, 7, 9),
        lines=(
            BoletaLine(
                "Servicio exento",
                Decimal("2"),
                Decimal("4500"),
                is_exempt=True,
            ),
        ),
    )


def test_builds_boleta_exenta_41_ted_and_dte() -> None:
    boleta = make_exempt_boleta()
    caf = make_trusted_caf(document_type=41)
    ted = TedBuilder().build(
        boleta,
        caf,
        generated_at=datetime(2026, 7, 9, 15, tzinfo=timezone.utc),
    )
    unsigned = DteBuilder().build(
        boleta,
        ted,
        signed_at=datetime(2026, 7, 9, 15, 1, tzinfo=timezone.utc),
    )

    root = etree.fromstring(unsigned.xml)
    namespace = {"sii": SII}
    assert unsigned.document_id == "F11T41"
    assert root.findtext(".//sii:TipoDTE", namespaces=namespace) == "41"
    assert root.findtext(".//sii:MntExe", namespaces=namespace) == "9000"
    assert root.findtext(".//sii:MntTotal", namespaces=namespace) == "9000"
    assert root.find(".//sii:MntNeto", namespace) is None
    assert root.find(".//sii:IVA", namespace) is None
    assert root.findtext(".//sii:IndExe", namespaces=namespace) == "1"
    assert b"<TD>41</TD>" in ted.dd
    assert ted.verify(caf)


def test_rejects_affected_line_or_wrong_caf_for_type_41() -> None:
    with pytest.raises(BoletaError, match="sólo puede contener ítems exentos"):
        BoletaExenta(
            issuer=make_exempt_boleta().issuer,
            folio=1,
            issued_on=date(2026, 7, 9),
            lines=(BoletaLine("Afecto", Decimal(1), Decimal(1000)),),
        )
    with pytest.raises(ValueError, match="tipo 41"):
        TedBuilder().build(
            make_exempt_boleta(),
            make_trusted_caf(document_type=39),
            generated_at=datetime(2026, 7, 9, 15, tzinfo=timezone.utc),
        )


def test_envio_boleta_groups_mixed_39_and_41() -> None:
    credential = make_signing_credential()
    _affected_caf, affected, affected_ted = make_document()
    affected_signed = XmlSigner().sign(
        DteBuilder().build(
            affected,
            affected_ted,
            signed_at=datetime(2026, 7, 9, 15, 1, tzinfo=timezone.utc),
        ),
        credential,
    )
    exempt = make_exempt_boleta()
    exempt_ted = TedBuilder().build(
        exempt,
        make_trusted_caf(document_type=41),
        generated_at=datetime(2026, 7, 9, 15, tzinfo=timezone.utc),
    )
    exempt_signed = XmlSigner().sign(
        DteBuilder().build(
            exempt,
            exempt_ted,
            signed_at=datetime(2026, 7, 9, 15, 1, tzinfo=timezone.utc),
        ),
        credential,
    )

    envelope = EnvioBoletaBuilder().build(
        (affected_signed, exempt_signed),
        issuer_rut="12345678-5",
        sender_rut="12345678-5",
        authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
        signed_at=datetime(2026, 7, 9, 15, 2, tzinfo=timezone.utc),
        credential=credential,
    )
    root = etree.fromstring(envelope.xml)
    namespace = {"sii": SII}
    subtotals = root.findall(".//sii:SubTotDTE", namespace)
    assert [item.findtext("sii:TpoDTE", namespaces=namespace) for item in subtotals] == [
        "39",
        "41",
    ]
    assert [item.findtext("sii:NroDTE", namespaces=namespace) for item in subtotals] == [
        "1",
        "1",
    ]
    assert XmlSigner().verify_raw(
        envelope.xml,
        target_tag=f"{{{SII}}}SetDTE",
        target_id=envelope.set_id,
    )
