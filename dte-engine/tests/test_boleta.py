from datetime import date
from decimal import Decimal

import pytest

from completo_dte.domain import BoletaAfecta, BoletaError, BoletaLine, Issuer


ISSUER = Issuer(
    rut="12.345.678-5",
    legal_name="RESTAURANTE SINTETICO SPA",
    business_activity="RESTAURANTES",
    activity_code=561000,
)


def test_calculates_gross_total_using_commercial_rounding() -> None:
    boleta = BoletaAfecta(
        issuer=ISSUER,
        folio=7,
        issued_on=date(2026, 7, 8),
        lines=(
            BoletaLine("Café", Decimal("1.5"), Decimal("1001")),
            BoletaLine("Menú", Decimal("2"), Decimal("5990"), Decimal("980")),
        ),
    )
    assert boleta.lines[0].gross_total == 1502
    assert boleta.total == 12_502
    assert boleta.net_total == 10_506
    assert boleta.vat_total == 1_996
    assert boleta.receiver_rut == "66666666-6"


def test_rejects_empty_sale() -> None:
    with pytest.raises(BoletaError, match="entre 1 y 60"):
        BoletaAfecta(
            issuer=ISSUER,
            folio=1,
            issued_on=date(2026, 7, 8),
            lines=(),
        )


def test_separates_exempt_amount_from_document_total() -> None:
    boleta = BoletaAfecta(
        issuer=ISSUER,
        folio=8,
        issued_on=date(2026, 7, 9),
        lines=(
            BoletaLine("item afecto 1", Decimal(8), Decimal(1590)),
            BoletaLine("item exento 2", Decimal(2), Decimal(1000), is_exempt=True),
        ),
        reference_code="SET",
        reference_reason="CASO-4",
    )
    assert boleta.exempt_total == 2000
    assert boleta.affected_gross_total == 12_720
    assert boleta.net_total == 10_689
    assert boleta.vat_total == 2_031
    assert boleta.total == 14_720


def test_reference_requires_code_and_reason_together() -> None:
    with pytest.raises(BoletaError, match="deben informarse juntos"):
        BoletaAfecta(
            issuer=ISSUER,
            folio=9,
            issued_on=date(2026, 7, 9),
            lines=(BoletaLine("Arroz", Decimal(5), Decimal(700)),),
            reference_code="SET",
        )


@pytest.mark.parametrize("issued_on", (date(2002, 7, 31), date(2051, 1, 1)))
def test_rejects_issue_date_outside_official_range(issued_on) -> None:
    with pytest.raises(BoletaError, match="fecha de emisión"):
        BoletaAfecta(
            issuer=ISSUER,
            folio=1,
            issued_on=issued_on,
            lines=(BoletaLine("Producto", Decimal(1), Decimal(1190)),),
        )
