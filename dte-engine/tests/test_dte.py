from datetime import date, datetime, timezone
from decimal import Decimal
from xml.etree import ElementTree

import pytest

from completo_dte.domain import (
    BoletaAfecta,
    BoletaLine,
    DteBuilder,
    Issuer,
    SignedTed,
    TedBuilder,
    TedError,
)
from factories import make_trusted_caf


def make_document():
    caf = make_trusted_caf()
    boleta = BoletaAfecta(
        issuer=Issuer(
            rut="12345678-5",
            legal_name="RESTAURANTE SINTETICO SPA",
            business_activity="RESTAURANTES",
            activity_code=561000,
            address="CALLE UNO 123",
            commune="SANTIAGO",
        ),
        folio=7,
        issued_on=date(2026, 7, 8),
        lines=(
            BoletaLine("Menú", Decimal("2"), Decimal("5990"), Decimal("980")),
            BoletaLine("Café", Decimal("1.5"), Decimal("1001")),
        ),
    )
    ted = TedBuilder().build(
        boleta,
        caf,
        generated_at=datetime(2026, 7, 8, 15, 30, tzinfo=timezone.utc),
    )
    return caf, boleta, ted


def test_builds_well_formed_unsigned_dte_39() -> None:
    caf, boleta, ted = make_document()
    dte = DteBuilder().build(
        boleta,
        ted,
        signed_at=datetime(2026, 7, 8, 15, 31, tzinfo=timezone.utc),
    )

    root = ElementTree.fromstring(dte.xml)
    namespace = {"sii": "http://www.sii.cl/SiiDte"}
    assert root.tag == "{http://www.sii.cl/SiiDte}DTE"
    assert root.findtext(".//sii:TipoDTE", namespaces=namespace) == "39"
    assert root.find(".//sii:IndMntNeto", namespace) is None
    assert root.findtext(".//sii:RznSocEmisor", namespaces=namespace) == "RESTAURANTE SINTETICO SPA"
    assert root.findtext(".//sii:MntTotal", namespaces=namespace) == str(boleta.total)
    assert len(root.findall(".//sii:Detalle", namespace)) == 2
    assert root.find(".//sii:Documento", namespace).get("ID") == "F7T39"
    assert ted.xml in dte.xml
    assert dte.xml.startswith(b'<?xml version="1.0" encoding="ISO-8859-1"?>')


def test_rejects_ted_for_another_total() -> None:
    _caf, boleta, ted = make_document()
    altered = SignedTed(
        xml=ted.xml,
        dd=ted.dd.replace(str(boleta.total).encode(), b"1"),
        signature=ted.signature,
    )
    with pytest.raises(TedError, match="MNT"):
        DteBuilder().build(
            boleta,
            altered,
            signed_at=datetime(2026, 7, 8, 15, 31, tzinfo=timezone.utc),
        )


def test_builds_certification_reference_exempt_line_and_unit_measure() -> None:
    caf = make_trusted_caf()
    boleta = BoletaAfecta(
        issuer=Issuer(
            rut="12345678-5",
            legal_name="RESTAURANTE SINTETICO SPA",
            business_activity="RESTAURANTES",
            activity_code=561000,
        ),
        folio=9,
        issued_on=date(2026, 7, 9),
        lines=(
            BoletaLine("item afecto 1", Decimal(8), Decimal(1590)),
            BoletaLine(
                "item exento 2",
                Decimal(2),
                Decimal(1000),
                is_exempt=True,
            ),
            BoletaLine("Arroz", Decimal(5), Decimal(700), unit_measure="Kg"),
        ),
        reference_code="SET",
        reference_reason="CASO-4",
    )
    ted = TedBuilder().build(
        boleta,
        caf,
        generated_at=datetime(2026, 7, 9, 15, 30, tzinfo=timezone.utc),
    )
    dte = DteBuilder().build(
        boleta,
        ted,
        signed_at=datetime(2026, 7, 9, 15, 31, tzinfo=timezone.utc),
    )

    root = ElementTree.fromstring(dte.xml)
    namespace = {"sii": "http://www.sii.cl/SiiDte"}
    details = root.findall(".//sii:Detalle", namespace)
    assert details[1].findtext("sii:IndExe", namespaces=namespace) == "1"
    assert details[2].findtext("sii:UnmdItem", namespaces=namespace) == "Kg"
    assert root.findtext(".//sii:MntExe", namespaces=namespace) == "2000"
    assert root.findtext(".//sii:MntNeto", namespaces=namespace) == "13630"
    assert root.findtext(".//sii:IVA", namespaces=namespace) == "2590"
    assert root.findtext(".//sii:CodRef", namespaces=namespace) == "SET"
    assert root.findtext(".//sii:RazonRef", namespaces=namespace) == "CASO-4"
