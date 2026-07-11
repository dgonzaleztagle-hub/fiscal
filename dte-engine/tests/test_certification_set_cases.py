from datetime import date, datetime, timezone
from decimal import Decimal
from xml.etree import ElementTree

import pytest

from completo_dte.domain import BoletaAfecta, BoletaLine, DteBuilder, Issuer, TedBuilder
from factories import make_trusted_caf


ISSUER = Issuer(
    rut="12345678-5",
    legal_name="EMISOR SINTETICO SPA",
    business_activity="SERVICIOS",
    activity_code=561000,
)
NAMESPACE = {"sii": "http://www.sii.cl/SiiDte"}


@pytest.mark.parametrize(
    ("case_number", "lines", "expected_total", "expected_exempt"),
    (
        (
            1,
            (
                BoletaLine("Cambio de aceite", Decimal(1), Decimal(19900)),
                BoletaLine("Alineacion y balanceo", Decimal(1), Decimal(9900)),
            ),
            29800,
            0,
        ),
        (
            2,
            (BoletaLine("Papel de regalo", Decimal(17), Decimal(120)),),
            2040,
            0,
        ),
        (
            3,
            (
                BoletaLine("Sandwic", Decimal(2), Decimal(1500)),
                BoletaLine("Bebida", Decimal(2), Decimal(550)),
            ),
            4100,
            0,
        ),
        (
            4,
            (
                BoletaLine("item afecto 1", Decimal(8), Decimal(1590)),
                BoletaLine(
                    "item exento 2",
                    Decimal(2),
                    Decimal(1000),
                    is_exempt=True,
                ),
            ),
            14720,
            2000,
        ),
        (
            5,
            (BoletaLine("Arroz", Decimal(5), Decimal(700), unit_measure="Kg"),),
            3500,
            0,
        ),
    ),
)
def test_generates_each_assigned_certification_case(
    case_number,
    lines,
    expected_total,
    expected_exempt,
) -> None:
    caf = make_trusted_caf()
    boleta = BoletaAfecta(
        issuer=ISSUER,
        folio=case_number,
        issued_on=date(2026, 7, 9),
        lines=lines,
        reference_code="SET",
        reference_reason=f"CASO-{case_number}",
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
    assert root.findtext(".//sii:MntTotal", namespaces=NAMESPACE) == str(expected_total)
    assert (
        root.findtext(".//sii:MntExe", default="0", namespaces=NAMESPACE)
        == str(expected_exempt)
    )
    assert root.findtext(".//sii:CodRef", namespaces=NAMESPACE) == "SET"
    assert (
        root.findtext(".//sii:RazonRef", namespaces=NAMESPACE)
        == f"CASO-{case_number}"
    )

    detail_names = [
        detail.findtext("sii:NmbItem", namespaces=NAMESPACE)
        for detail in root.findall(".//sii:Detalle", NAMESPACE)
    ]
    assert detail_names == [line.name for line in lines]

    if case_number == 5:
        assert root.findtext(".//sii:UnmdItem", namespaces=NAMESPACE) == "Kg"
