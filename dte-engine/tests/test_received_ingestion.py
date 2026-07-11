from importlib.resources import files

from completo_dte.application import ReceivedDocumentIngestionService
from completo_dte.domain import ReceivedDocumentValidator
from completo_dte.infrastructure import FolioLedger
from test_official_invoice_schema import signed_invoice


def test_upload_email_and_connector_share_one_idempotent_ingestion_path(tmp_path) -> None:
    database = tmp_path / "ingestion.sqlite3"
    ledger = FolioLedger(database)
    ledger.migrate()
    schema = files("completo_dte").joinpath(
        "resources", "sii", "schema_dte_v10", "DTE_v10.xsd"
    )
    service = ReceivedDocumentIngestionService(
        ledger=ledger,
        validator=ReceivedDocumentValidator(schema),
        resolve_receiver_rut=lambda tenant: "11111111-1" if tenant == "tenant-a" else "22222222-2",
    )
    signed, _credential, _timestamp = signed_invoice()
    upload = service.ingest(
        tenant_id="tenant-a", xml=signed.xml, source="upload"
    )
    email_retry = service.ingest(
        tenant_id="tenant-a", xml=signed.xml, source="email"
    )
    connector_retry = service.ingest(
        tenant_id="tenant-a",
        xml=signed.xml,
        source="official_connector",
        sii_received_at="2026-07-10T10:30:00-04:00",
    )

    assert email_retry == upload
    assert upload.source == "upload"
    assert upload.sii_received_at is None
    assert connector_retry == upload
    observation = ledger.latest_sii_reception_observation(
        upload.id, tenant_id="tenant-a"
    )
    assert observation.sii_received_at == "2026-07-10T10:30:00-04:00"
