from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from completo_dte.domain import (
    BoletaAfecta,
    BoletaLine,
    CafLoader,
    Issuer,
    SignedTed,
    TedBuilder,
    TedError,
)
from factories import make_synthetic_caf, make_trusted_caf


def make_boleta(*, folio: int = 7, issuer_rut: str = "12345678-5") -> BoletaAfecta:
    return BoletaAfecta(
        issuer=Issuer(
            rut=issuer_rut,
            legal_name="RESTAURANTE SINTETICO SPA",
            business_activity="RESTAURANTES",
            activity_code=561000,
        ),
        folio=folio,
        issued_on=date(2026, 7, 8),
        lines=(BoletaLine("Menú & café <especial>", Decimal(2), Decimal(5990)),),
    )


def test_builds_and_independently_verifies_ted_signature() -> None:
    caf = make_trusted_caf()
    signed = TedBuilder().build(
        make_boleta(),
        caf,
        generated_at=datetime(2026, 7, 8, 15, 30, 45, tzinfo=timezone.utc),
    )

    assert signed.verify(caf)
    assert b"<TD>39</TD><F>7</F><FE>2026-07-08</FE>" in signed.dd
    assert b"<MNT>11980</MNT>" in signed.dd
    assert b"Men\xfa &amp; caf\xe9 &lt;especial&gt;" in signed.dd
    assert b"<TSTED>2026-07-08T11:30:45</TSTED>" in signed.dd
    assert caf.caf_xml in signed.dd
    assert b'<FRMT algoritmo="SHA1withRSA">' in signed.xml


def test_detects_tampered_dd() -> None:
    caf = make_trusted_caf()
    signed = TedBuilder().build(
        make_boleta(),
        caf,
        generated_at=datetime(2026, 7, 8, 15, tzinfo=timezone.utc),
    )
    tampered = SignedTed(
        xml=signed.xml,
        dd=signed.dd.replace(b"<MNT>11980</MNT>", b"<MNT>1</MNT>"),
        signature=signed.signature,
    )
    assert not tampered.verify(caf)


@pytest.mark.parametrize(
    ("caf_kwargs", "message"),
    [
        ({"issuer_rut": "6927045-K"}, "otro emisor"),
        ({"document_type": 41}, "tipo 39"),
        ({"folio_from": 20, "folio_to": 30}, "fuera del rango"),
    ],
)
def test_rejects_caf_that_does_not_authorize_document(caf_kwargs: dict, message: str) -> None:
    caf = make_trusted_caf(**caf_kwargs)
    with pytest.raises(TedError, match=message):
        TedBuilder().build(
            make_boleta(),
            caf,
            generated_at=datetime(2026, 7, 8, 15, tzinfo=timezone.utc),
        )


def test_requires_timezone_for_ted_timestamp() -> None:
    caf = make_trusted_caf()
    with pytest.raises(TedError, match="zona horaria"):
        TedBuilder().build(
            make_boleta(),
            caf,
            generated_at=datetime(2026, 7, 8, 12),
        )


def test_refuses_structurally_valid_but_unauthenticated_caf() -> None:
    untrusted = CafLoader().load(make_synthetic_caf())
    with pytest.raises(TedError, match="FRMA validada"):
        TedBuilder().build(
            make_boleta(),
            untrusted,  # type: ignore[arg-type]
            generated_at=datetime(2026, 7, 8, 15, tzinfo=timezone.utc),
        )
