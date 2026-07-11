"""Agrupa boletas firmadas en EnvioBOLETA y RCOF inmutables."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
import hashlib

from lxml import etree

from completo_dte.domain import (
    DailyFolio,
    DailySummaryBuilder,
    EnvelopeAuthorization,
    EnvioBoletaBuilder,
    SigningCredential,
    SignedDte,
)
from completo_dte.infrastructure import (
    FiscalDocumentRecord,
    FiscalEnvelopeRecord,
    FolioLedger,
)


class BoletaBatchCoordinator:
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
            limit=500,
        )
        if not records:
            return None
        fingerprint = _records_fingerprint(records)
        set_id = f"SetB_{fingerprint[:20]}"
        envelope = EnvioBoletaBuilder().build(
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
            kind="envio_boleta",
            document_id=set_id,
            signed_xml=envelope.xml,
            document_record_ids=tuple(record.id for record in records),
        )

    def prepare_daily_summary(
        self,
        *,
        tenant_id: str,
        taxpayer_rut: str,
        issued_on: date,
        sequence: int = 1,
    ) -> FiscalEnvelopeRecord | None:
        pending = self._ledger.pending_envelope_documents(
            tenant_id=tenant_id,
            taxpayer_rut=taxpayer_rut,
            relation_kind="consumption",
            limit=10_000,
        )
        pairs = tuple(
            (record, daily)
            for record in pending
            if (daily := _daily_folio(record)).issued_on == issued_on
        )
        if not pairs:
            return None
        records = tuple(record for record, _daily in pairs)
        folios = tuple(daily for _record, daily in pairs)
        document_id = f"RCOF_{issued_on:%Y%m%d}_S{sequence:03d}"
        summary = DailySummaryBuilder().build(
            folios,
            issuer_rut=taxpayer_rut,
            sender_rut=self._sender_rut,
            authorization=self._authorization,
            sequence=sequence,
            signed_at=self._clock(),
            credential=self._credential,
            document_id=document_id,
        )
        return self._ledger.persist_envelope_with_documents(
            tenant_id=tenant_id,
            taxpayer_rut=taxpayer_rut,
            kind="rcof",
            document_id=document_id,
            signed_xml=summary.xml,
            document_record_ids=tuple(record.id for record in records),
        )


def _records_fingerprint(records: tuple[FiscalDocumentRecord, ...]) -> str:
    canonical = "|".join(
        f"{record.id}:{record.document_id}:{record.xml_sha256}" for record in records
    )
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _daily_folio(record: FiscalDocumentRecord) -> DailyFolio:
    try:
        root = etree.fromstring(
            record.signed_xml,
            etree.XMLParser(resolve_entities=False, no_network=True),
        )
        document_type = int(_one_text(root, "TipoDTE"))
        folio = int(_one_text(root, "Folio"))
        issued_on = date.fromisoformat(_one_text(root, "FchEmis"))
        total = int(_one_text(root, "MntTotal"))
        net = int(_optional_text(root, "MntNeto") or 0)
        vat = int(_optional_text(root, "IVA") or 0)
        exempt = int(_optional_text(root, "MntExe") or 0)
    except (ValueError, etree.XMLSyntaxError) as exc:
        raise ValueError(f"El documento {record.document_id} no sirve para RCOF") from exc
    if document_type != record.document_type or folio != record.folio:
        raise ValueError(f"La identidad XML de {record.document_id} no coincide con el ledger")
    return DailyFolio(
        document_type=document_type,
        folio=folio,
        issued_on=issued_on,
        net_amount=net,
        vat_amount=vat,
        exempt_amount=exempt,
        total_amount=total,
    )


def _one_text(root: etree._Element, name: str) -> str:
    values = root.xpath(f"//*[local-name()='{name}']/text()")
    if len(values) != 1 or not str(values[0]).strip():
        raise ValueError(f"XML sin un único {name}")
    return str(values[0]).strip()


def _optional_text(root: etree._Element, name: str) -> str | None:
    values = root.xpath(f"//*[local-name()='{name}']/text()")
    if len(values) > 1:
        raise ValueError(f"XML con {name} repetido")
    return str(values[0]).strip() if values else None
