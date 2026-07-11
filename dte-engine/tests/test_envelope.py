from datetime import date, datetime, timezone
from dataclasses import replace

from lxml import etree
import pytest

from completo_dte.domain import (
    DteBuilder,
    EnvelopeAuthorization,
    EnvioBoletaBuilder,
    XmlSigner,
)
from completo_dte.domain.xml_signature import SII
from factories import make_signing_credential
from test_dte import make_document


def make_signed_document(credential):
    _caf, boleta, ted = make_document()
    unsigned = DteBuilder().build(
        boleta,
        ted,
        signed_at=datetime(2026, 7, 8, 15, 31, tzinfo=timezone.utc),
    )
    return XmlSigner().sign(unsigned, credential)


def test_builds_and_signs_envio_boleta() -> None:
    credential = make_signing_credential()
    document = make_signed_document(credential)
    envelope = EnvioBoletaBuilder().build(
        (document,),
        issuer_rut="12345678-5",
        sender_rut="12345678-5",
        authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
        signed_at=datetime(2026, 7, 8, 15, 32, tzinfo=timezone.utc),
        credential=credential,
    )

    root = etree.fromstring(envelope.xml)
    namespace = {"sii": SII}
    assert root.tag == f"{{{SII}}}EnvioBOLETA"
    assert root.findtext(".//sii:RutReceptor", namespaces=namespace) == "60803000-K"
    assert root.findtext(".//sii:TpoDTE", namespaces=namespace) == "39"
    assert root.findtext(".//sii:NroDTE", namespaces=namespace) == "1"
    assert len(root.findall(".//sii:DTE", namespace)) == 1
    assert XmlSigner().verify(document)
    assert XmlSigner().verify_raw(
        envelope.xml,
        target_tag=f"{{{SII}}}SetDTE",
        target_id=envelope.set_id,
    )


def test_rejects_tampered_or_repeated_document_before_signing_envelope() -> None:
    credential = make_signing_credential()
    document = make_signed_document(credential)
    builder = EnvioBoletaBuilder()
    kwargs = dict(
        issuer_rut="12345678-5",
        sender_rut="12345678-5",
        authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
        signed_at=datetime(2026, 7, 8, 15, 32, tzinfo=timezone.utc),
        credential=credential,
    )

    tampered = replace(
        document,
        xml=document.xml.replace(b"<MntTotal>", b"<MntTotal>1", 1),
    )
    with pytest.raises(ValueError, match="firma"):
        builder.build((tampered,), **kwargs)
    with pytest.raises(ValueError, match="repetir"):
        builder.build((document, document), **kwargs)
