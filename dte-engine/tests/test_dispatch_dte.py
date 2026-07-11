from dataclasses import replace
from datetime import date, datetime, time, timezone
from decimal import Decimal
from importlib.resources import files
from xml.etree import ElementTree

import pytest

from completo_dte.domain import (
    DispatchAccount,
    DispatchDocument,
    DispatchDteBuilder,
    DispatchError,
    DispatchReason,
    DispatchTransport,
    EnvelopeAuthorization,
    EnvioDteBuilder,
    FiscalLine,
    Issuer,
    Party,
    PriceMode,
    TaxCategory,
    TedBuilder,
    XmlSchemaValidator,
    XmlSigner,
)
from factories import make_signing_credential, make_trusted_caf


def make_guide(*, internal: bool = False) -> DispatchDocument:
    issuer = Issuer(
        rut="12345678-5",
        legal_name="SOFTWARE SINTETICO SPA",
        business_activity="DESARROLLO DE SOFTWARE",
        activity_code=620100,
        address="AVENIDA UNO 100",
        commune="SANTIAGO",
    )
    receiver = Party(
        rut=issuer.rut if internal else "11111111-1",
        legal_name=issuer.legal_name if internal else "CLIENTE SINTETICO SPA",
        business_activity="DESARROLLO DE SOFTWARE" if internal else "COMERCIO",
        address="BODEGA DOS 200",
        commune="PROVIDENCIA",
        city="SANTIAGO",
    )
    return DispatchDocument(
        issuer=issuer,
        receiver=receiver,
        folio=7,
        issued_on=date(2026, 7, 10),
        reason=(DispatchReason.INTERNAL_TRANSFER if internal else DispatchReason.SALE),
        dispatch_account=None if internal else DispatchAccount.ISSUER_TO_BUYER,
        transport=DispatchTransport(
            vehicle_plate="ABCD12",
            carrier_rut="11111111-1",
            driver_rut="22222222-2",
            driver_name="CHOFER SINTETICO",
            destination_address="BODEGA DOS 200",
            destination_commune="PROVIDENCIA",
            destination_city="SANTIAGO",
        ),
        lines=(
            FiscalLine(
                name="Equipo",
                quantity=Decimal("2"),
                unit_price=Decimal("10000") if not internal else Decimal(0),
                tax_category=(
                    TaxCategory.AFFECTED if not internal else TaxCategory.NON_BILLABLE
                ),
                price_mode=PriceMode.NET,
                unit_measure="UN",
            ),
        ),
    )


def signed_guide(*, internal: bool = False):
    guide = make_guide(internal=internal)
    caf = make_trusted_caf(document_type=52)
    credential = make_signing_credential()
    timestamp = datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc)
    ted = TedBuilder().build(guide, caf, generated_at=timestamp)
    unsigned = DispatchDteBuilder().build(guide, ted, signed_at=timestamp)
    return guide, unsigned, XmlSigner().sign(unsigned, credential), credential, timestamp


def test_builds_valued_sale_guide() -> None:
    guide, unsigned, signed, credential, _timestamp = signed_guide()
    root = ElementTree.fromstring(unsigned.xml)
    ns = {"sii": "http://www.sii.cl/SiiDte"}

    assert root.findtext(".//sii:TipoDespacho", namespaces=ns) == "2"
    assert root.findtext(".//sii:IndTraslado", namespaces=ns) == "1"
    assert root.findtext(".//sii:Patente", namespaces=ns) == "ABCD12"
    assert root.findtext(".//sii:RUTChofer", namespaces=ns) == "22222222-2"
    assert root.findtext(".//sii:MntNeto", namespaces=ns) == "20000"
    assert root.findtext(".//sii:IVA", namespaces=ns) == "3800"
    assert root.findtext(".//sii:MntTotal", namespaces=ns) == "23800"
    assert guide.total == 23800
    assert XmlSigner().verify_with_certificate(signed, credential.certificate)


def test_builds_internal_transfer_without_price_or_dispatch_account() -> None:
    guide, unsigned, _signed, _credential, _timestamp = signed_guide(internal=True)
    root = ElementTree.fromstring(unsigned.xml)
    ns = {"sii": "http://www.sii.cl/SiiDte"}

    assert root.find(".//sii:TipoDespacho", ns) is None
    assert root.findtext(".//sii:IndTraslado", namespaces=ns) == "5"
    assert root.find(".//sii:PrcItem", ns) is None
    assert root.find(".//sii:IndExe", ns) is None
    assert root.findtext(".//sii:MontoItem", namespaces=ns) == "0"
    assert root.findtext(".//sii:MntTotal", namespaces=ns) == "0"
    assert guide.total == 0


@pytest.mark.parametrize("internal", [False, True])
def test_guide_and_envelope_validate_against_pinned_official_xsd(internal: bool) -> None:
    _guide, _unsigned, signed, credential, timestamp = signed_guide(internal=internal)
    schema_root = files("completo_dte").joinpath("resources", "sii", "schema_dte_v10")
    XmlSchemaValidator(schema_root.joinpath("DTE_v10.xsd")).validate(signed.xml)
    envelope = EnvioDteBuilder().build(
        (signed,),
        issuer_rut="12345678-5",
        sender_rut="12345678-5",
        authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
        signed_at=timestamp,
        credential=credential,
    )
    XmlSchemaValidator(schema_root.joinpath("EnvioDTE_v10.xsd")).validate(envelope.xml)


def test_future_transport_fields_fail_closed_until_official_xsd_changes() -> None:
    guide = replace(
        make_guide(),
        transport=replace(
            make_guide().transport,
            trailer_plate="WXYZ99",
            departure_on=date(2026, 11, 1),
            departure_time=time(10, 30),
        ),
    )
    caf = make_trusted_caf(document_type=52)
    timestamp = datetime(2026, 11, 1, 13, 30, tzinfo=timezone.utc)
    ted = TedBuilder().build(guide, caf, generated_at=timestamp)

    with pytest.raises(DispatchError, match="XSD oficial vigente"):
        DispatchDteBuilder().build(guide, ted, signed_at=timestamp)


def test_internal_transfer_rejects_cross_taxpayer_receiver() -> None:
    with pytest.raises(DispatchError, match="emisor como receptor"):
        replace(
            make_guide(internal=True),
            receiver=Party(
                rut="11111111-1",
                legal_name="OTRO",
                business_activity="COMERCIO",
                address="CALLE 1",
                commune="SANTIAGO",
            ),
        )
