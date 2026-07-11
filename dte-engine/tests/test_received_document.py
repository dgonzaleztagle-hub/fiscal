from importlib.resources import files

import pytest

from completo_dte.domain import ReceivedDocumentError, ReceivedDocumentValidator
from test_official_invoice_schema import signed_invoice


def validator() -> ReceivedDocumentValidator:
    schema = files("completo_dte").joinpath(
        "resources", "sii", "schema_dte_v10", "DTE_v10.xsd"
    )
    return ReceivedDocumentValidator(schema)


def test_validates_signature_schema_receiver_and_extracts_received_dte() -> None:
    signed, _credential, _timestamp = signed_invoice()
    received = validator().validate(signed.xml, expected_receiver_rut="11111111-1")

    assert received.document_id == "F7T33"
    assert received.document_type == 33
    assert received.folio == 7
    assert received.issuer_rut == "12345678-5"
    assert received.receiver_rut == "11111111-1"
    assert received.total == 21420
    assert received.lines[0].line_number == 1
    assert received.lines[0].name == "Servicio mensual"
    assert received.lines[0].amount == 18000
    assert len(received.xml_sha256) == 64


def test_rejects_dte_for_another_tenant() -> None:
    signed, _credential, _timestamp = signed_invoice()
    with pytest.raises(ReceivedDocumentError, match="otro contribuyente"):
        validator().validate(signed.xml, expected_receiver_rut="22222222-2")


def test_rejects_tampering_even_when_xml_remains_well_formed() -> None:
    signed, _credential, _timestamp = signed_invoice()
    tampered = signed.xml.replace(b"<MntTotal>21420</MntTotal>", b"<MntTotal>99999</MntTotal>")
    with pytest.raises(ReceivedDocumentError, match="firma XMLDSig"):
        validator().validate(tampered, expected_receiver_rut="11111111-1")


def test_rejects_external_entities_without_network_or_file_resolution() -> None:
    malicious = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY leak SYSTEM "file:///etc/passwd">]><x>&leak;</x>'
    with pytest.raises(ReceivedDocumentError):
        validator().validate(malicious, expected_receiver_rut="11111111-1")
