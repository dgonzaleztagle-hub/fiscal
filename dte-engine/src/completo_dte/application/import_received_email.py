"""Procesamiento aislado de adjuntos; no conecta ni lee buzones por sí mismo."""

from dataclasses import dataclass

from .ingest_received_document import ReceivedDocumentIngestionService


@dataclass(frozen=True)
class InboundAttachment:
    filename: str
    content_type: str
    payload: bytes


@dataclass(frozen=True)
class AttachmentImportResult:
    filename: str
    status: str
    document_record_id: str | None = None
    error: str | None = None


class ReceivedEmailAttachmentProcessor:
    def __init__(self, ingestion: ReceivedDocumentIngestionService) -> None:
        self._ingestion = ingestion

    def process(
        self, *, tenant_id: str, attachments: tuple[InboundAttachment, ...]
    ) -> tuple[AttachmentImportResult, ...]:
        results = []
        for attachment in attachments:
            is_xml = attachment.content_type in {"application/xml", "text/xml"} or (
                attachment.filename.lower().endswith(".xml")
            )
            if not is_xml:
                results.append(AttachmentImportResult(attachment.filename, "ignored"))
                continue
            try:
                record = self._ingestion.ingest(
                    tenant_id=tenant_id,
                    xml=attachment.payload,
                    source="email",
                )
                results.append(
                    AttachmentImportResult(
                        attachment.filename, "imported", record.id, None
                    )
                )
            except ValueError as exc:
                results.append(
                    AttachmentImportResult(
                        attachment.filename, "rejected", None, str(exc)
                    )
                )
        return tuple(results)
