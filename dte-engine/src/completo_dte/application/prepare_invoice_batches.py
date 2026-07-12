"""Agrupa facturas firmadas en sobres EnvioDTE inmutables."""

from collections.abc import Callable
from datetime import datetime
import hashlib

from completo_dte.domain import (
    EnvelopeAuthorization,
    EnvioDteBuilder,
    SigningCredential,
    SignedDte,
)
from completo_dte.infrastructure import FiscalEnvelopeRecord, FolioLedger


class InvoiceBatchCoordinator:
    def __init__(
        self,
        *,
        ledger: FolioLedger,
        credential: SigningCredential,
        authorization: EnvelopeAuthorization,
        sender_rut: str,
        clock: Callable[[], datetime],
    ) -> None:
        self._ledger = ledger
        self._credential = credential
        self._authorization = authorization
        self._sender_rut = sender_rut
        self._clock = clock

    def prepare_dispatch(
        self,
        *,
        tenant_id: str,
        taxpayer_rut: str,
    ) -> FiscalEnvelopeRecord | None:
        records = self._ledger.pending_envelope_documents(
            tenant_id=tenant_id,
            taxpayer_rut=taxpayer_rut,
            relation_kind="dispatch",
            document_types=(33, 34),
            limit=500,
        )
        if not records:
            return None
        canonical = "|".join(
            f"{record.id}:{record.document_id}:{record.xml_sha256}"
            for record in records
        )
        fingerprint = hashlib.sha256(canonical.encode("ascii")).hexdigest()
        set_id = f"SetF_{fingerprint[:20]}"
        envelope = EnvioDteBuilder().build(
            tuple(
                SignedDte(xml=record.signed_xml, document_id=record.document_id)
                for record in records
            ),
            issuer_rut=taxpayer_rut,
            sender_rut=self._sender_rut,
            authorization=self._authorization,
            signed_at=self._clock(),
            credential=self._credential,
            set_id=set_id,
        )
        return self._ledger.persist_envelope_with_documents(
            tenant_id=tenant_id,
            taxpayer_rut=taxpayer_rut,
            kind="envio_dte",
            document_id=set_id,
            signed_xml=envelope.xml,
            document_record_ids=tuple(record.id for record in records),
        )
