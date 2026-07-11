from datetime import datetime, timezone

from lxml import etree

from completo_dte.domain import DteBuilder, SignedDte, XmlSigner
from factories import make_signing_credential
from test_dte import make_document


def make_unsigned_dte():
    _caf, boleta, ted = make_document()
    return DteBuilder().build(
        boleta,
        ted,
        signed_at=datetime(2026, 7, 8, 15, 31, tzinfo=timezone.utc),
    )


def test_signs_and_independently_verifies_complete_dte() -> None:
    unsigned = make_unsigned_dte()
    signed = XmlSigner().sign(unsigned, make_signing_credential())

    assert XmlSigner().verify(signed)
    root = etree.fromstring(signed.xml)
    assert root.find("{http://www.w3.org/2000/09/xmldsig#}Signature") is not None
    assert b'<Reference URI="#F7T39">' in signed.xml
    assert b"<X509Certificate>" in signed.xml


def test_detects_document_tampering_after_signature() -> None:
    unsigned = make_unsigned_dte()
    signed = XmlSigner().sign(unsigned, make_signing_credential())
    tampered = SignedDte(
        xml=signed.xml.replace(b"<MntTotal>12502</MntTotal>", b"<MntTotal>1</MntTotal>"),
        document_id=signed.document_id,
    )
    assert not XmlSigner().verify(tampered)


def test_self_consistent_signature_is_rejected_for_unexpected_certificate() -> None:
    unsigned = make_unsigned_dte()
    expected = make_signing_credential()
    attacker = make_signing_credential()
    signed = XmlSigner().sign(unsigned, attacker)

    assert XmlSigner().verify(signed)
    assert not XmlSigner().verify_with_certificate(signed, expected.certificate)
    assert XmlSigner().verify_with_certificate(signed, attacker.certificate)


def test_rejects_duplicate_target_id_signature_wrapping() -> None:
    unsigned = make_unsigned_dte()
    credential = make_signing_credential()
    signed = XmlSigner().sign(unsigned, credential)
    wrapped = SignedDte(
        xml=signed.xml.replace(
            b"</DTE>",
            b'<Injected ID="F7T39"></Injected></DTE>',
        ),
        document_id=signed.document_id,
    )
    assert not XmlSigner().verify_with_certificate(wrapped, credential.certificate)
