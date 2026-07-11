from lxml import etree
import pytest

from completo_dte.adapters.sii.received_registry import (
    ReceivedRegistryCodecError,
    ReceivedRegistrySoapCodec,
)


def local_text(root, name):
    values = root.xpath("//*[local-name()=$name]/text()", name=name)
    return values[0] if values else None


def test_builds_all_five_official_action_codes_without_network() -> None:
    codec = ReceivedRegistrySoapCodec()
    for action in ("ACD", "ERM", "RCD", "RFP", "RFT"):
        root = etree.fromstring(
            codec.action_request(
                issuer_rut="12345678-5",
                document_type=33,
                folio=7,
                action_code=action,
            )
        )
        assert local_text(root, "rutEmisor") == "12345678"
        assert local_text(root, "dvEmisor") == "5"
        assert local_text(root, "tipoDoc") == "33"
        assert local_text(root, "folio") == "7"
        assert local_text(root, "accionDoc") == action


def test_builds_event_and_authoritative_reception_date_queries() -> None:
    codec = ReceivedRegistrySoapCodec()
    events = etree.fromstring(
        codec.events_request(issuer_rut="12345678-5", document_type=34, folio=9)
    )
    reception = etree.fromstring(
        codec.reception_date_request(
            issuer_rut="12345678-5", document_type=34, folio=9
        )
    )
    assert events.xpath("count(//*[local-name()='listarEventosHistDoc'])") == 1
    assert reception.xpath("count(//*[local-name()='consultarFechaRecepcionSii'])") == 1


def test_parses_synthetic_action_and_reception_responses() -> None:
    codec = ReceivedRegistrySoapCodec()
    result = codec.parse_action_response(
        b"<Envelope><Body><response><codResp>0</codResp><descResp>Accion completada OK</descResp></response></Body></Envelope>"
    )
    reception = codec.parse_reception_date(
        b"<Envelope><Body><fechaRecepcionSii>2026-07-10T10:30:00-04:00</fechaRecepcionSii></Body></Envelope>"
    )
    assert result.successful
    assert result.code == 0
    assert reception == "2026-07-10T10:30:00-04:00"


def test_rejects_unsupported_types_and_ambiguous_responses() -> None:
    codec = ReceivedRegistrySoapCodec()
    with pytest.raises(ReceivedRegistryCodecError, match="sólo admite"):
        codec.action_request(
            issuer_rut="12345678-5", document_type=52, folio=1, action_code="ACD"
        )
    with pytest.raises(ReceivedRegistryCodecError, match="ambigua"):
        codec.parse_action_response(b"<x><codResp>0</codResp></x>")
