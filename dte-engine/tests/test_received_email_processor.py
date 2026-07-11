from importlib.resources import files

from completo_dte.application import (
    InboundAttachment,
    ReceivedDocumentIngestionService,
    ReceivedEmailAttachmentProcessor,
)
from completo_dte.domain import ReceivedDocumentValidator
from completo_dte.infrastructure import FolioLedger
from test_official_invoice_schema import signed_invoice


def test_email_batch_isolates_valid_invalid_and_non_xml_attachments(tmp_path) -> None:
    ledger = FolioLedger(tmp_path / "email.sqlite3")
    ledger.migrate()
    schema = files("completo_dte").joinpath(
        "resources", "sii", "schema_dte_v10", "DTE_v10.xsd"
    )
    ingestion = ReceivedDocumentIngestionService(
        ledger=ledger,
        validator=ReceivedDocumentValidator(schema),
        resolve_receiver_rut=lambda _tenant: "11111111-1",
    )
    signed, _credential, _timestamp = signed_invoice()
    results = ReceivedEmailAttachmentProcessor(ingestion).process(
        tenant_id="tenant-a",
        attachments=(
            InboundAttachment("factura.xml", "application/xml", signed.xml),
            InboundAttachment("malformed.xml", "application/xml", b"<not-dte/>"),
            InboundAttachment("factura.pdf", "application/pdf", b"%PDF-demo"),
        ),
    )
    assert [result.status for result in results] == ["imported", "rejected", "ignored"]
    assert results[0].document_record_id is not None
    assert results[1].error
