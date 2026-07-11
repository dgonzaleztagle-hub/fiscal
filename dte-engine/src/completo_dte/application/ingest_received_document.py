"""Entrada común para upload, correo y futuro conector oficial."""

from collections.abc import Callable

from completo_dte.domain import ReceivedDocumentValidator
from completo_dte.infrastructure import (
    FolioLedger,
    ReceivedFiscalDocumentRecord,
)


class ReceivedDocumentIngestionService:
    def __init__(
        self,
        *,
        ledger: FolioLedger,
        validator: ReceivedDocumentValidator,
        resolve_receiver_rut: Callable[[str], str],
    ) -> None:
        self._ledger = ledger
        self._validator = validator
        self._resolve_receiver_rut = resolve_receiver_rut

    def ingest(
        self,
        *,
        tenant_id: str,
        xml: bytes,
        source: str,
        sii_received_at: str | None = None,
    ) -> ReceivedFiscalDocumentRecord:
        received = self._validator.validate(
            xml,
            expected_receiver_rut=self._resolve_receiver_rut(tenant_id),
        )
        return self._ledger.import_received_document(
            tenant_id=tenant_id,
            document=received,
            source=source,
            sii_received_at=sii_received_at,
        )
