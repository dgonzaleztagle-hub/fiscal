from datetime import date, datetime, timezone
from dataclasses import replace

from lxml import etree
import pytest

from completo_dte.domain import (
    DocumentType,
    EnvelopeAuthorization,
    EnvioDteBuilder,
    InvoiceDteBuilder,
    TedBuilder,
    XmlSigner,
)
from completo_dte.domain.xml_signature import SII
from factories import make_signing_credential, make_trusted_caf
from test_invoice_dte import make_invoice


def signed_invoice(document_type, credential):
    invoice = make_invoice(document_type)
    caf = make_trusted_caf(document_type=int(document_type))
    timestamp = datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc)
    ted = TedBuilder().build(invoice, caf, generated_at=timestamp)
    unsigned = InvoiceDteBuilder().build(invoice, ted, signed_at=timestamp)
    return XmlSigner().sign(unsigned, credential)


def test_builds_mixed_factura_envio_dte_and_signs_set() -> None:
    credential = make_signing_credential()
    affected = signed_invoice(DocumentType.FACTURA_AFECTA, credential)
    exempt = signed_invoice(DocumentType.FACTURA_EXENTA, credential)
    envelope = EnvioDteBuilder().build(
        (affected, exempt),
        issuer_rut="12345678-5",
        sender_rut="12345678-5",
        authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
        signed_at=datetime(2026, 7, 10, 15, 32, tzinfo=timezone.utc),
        credential=credential,
        set_id="Facturas_1",
    )

    root = etree.fromstring(envelope.xml)
    namespace = {"sii": SII}
    subtotals = {
        node.findtext("sii:TpoDTE", namespaces=namespace): node.findtext(
            "sii:NroDTE", namespaces=namespace
        )
        for node in root.findall(".//sii:SubTotDTE", namespace)
    }
    assert root.tag == f"{{{SII}}}EnvioDTE"
    assert root.findtext(".//sii:RutReceptor", namespaces=namespace) == "60803000-K"
    assert subtotals == {"33": "1", "34": "1"}
    assert len(root.findall(".//sii:DTE", namespace)) == 2
    assert XmlSigner().verify_raw(
        envelope.xml,
        target_tag=f"{{{SII}}}SetDTE",
        target_id=envelope.set_id,
    )


def test_builds_recipient_exchange_and_rejects_crossed_receiver() -> None:
    credential = make_signing_credential()
    document = signed_invoice(DocumentType.FACTURA_AFECTA, credential)
    kwargs = dict(
        issuer_rut="12345678-5",
        sender_rut="12345678-5",
        receiver_rut="11111111-1",
        authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
        signed_at=datetime(2026, 7, 10, 15, 32, tzinfo=timezone.utc),
        credential=credential,
    )
    exchange = EnvioDteBuilder().build((document,), **kwargs)
    root = etree.fromstring(exchange.xml)
    assert root.xpath("//*[local-name()='RutReceptor']/text()") == ["11111111-1"]

    other_invoice = make_invoice(DocumentType.FACTURA_AFECTA)
    other_invoice = replace(
        other_invoice,
        receiver=replace(other_invoice.receiver, rut="76192083-9"),
    )
    timestamp = datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc)
    other_caf = make_trusted_caf(document_type=33)
    other_ted = TedBuilder().build(other_invoice, other_caf, generated_at=timestamp)
    crossed = XmlSigner().sign(
        InvoiceDteBuilder().build(other_invoice, other_ted, signed_at=timestamp),
        credential,
    )
    with pytest.raises(ValueError, match="otro receptor"):
        EnvioDteBuilder().build((crossed,), **kwargs)
