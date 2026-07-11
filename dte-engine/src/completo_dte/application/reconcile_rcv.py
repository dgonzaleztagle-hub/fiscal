"""Conciliación semántica entre XML recibidos y snapshot RCV."""

from dataclasses import dataclass
from enum import StrEnum

from completo_dte.infrastructure import FolioLedger, RcvRepository, RcvSnapshotRecord


class RcvDifferenceType(StrEnum):
    MATCH = "match"
    TOTAL_MISMATCH = "total_mismatch"
    ONLY_XML = "only_xml"
    ONLY_RCV = "only_rcv"


@dataclass(frozen=True)
class RcvDifference:
    kind: RcvDifferenceType
    issuer_rut: str
    document_type: int
    folio: int
    xml_total: int | None
    rcv_total: int | None


class RcvReconciliationService:
    def __init__(self, *, ledger: FolioLedger, repository: RcvRepository) -> None:
        self._ledger = ledger
        self._repository = repository

    def reconcile(
        self, *, tenant_id: str, snapshot: RcvSnapshotRecord
    ) -> tuple[RcvDifference, ...]:
        rcv_entries = self._repository.entries(snapshot.id, tenant_id=tenant_id)
        xml_records = self._ledger.list_received_documents(
            tenant_id=tenant_id, limit=200
        )
        rcv = {record.entry.identity: record.entry for record in rcv_entries}
        xml = {
            (record.issuer_rut, record.document_type, record.folio): record
            for record in xml_records
            if record.issued_on.startswith(snapshot.period)
        }
        differences = []
        for identity in sorted(set(rcv) | set(xml)):
            rcv_entry = rcv.get(identity)
            xml_record = xml.get(identity)
            if rcv_entry is None:
                kind = RcvDifferenceType.ONLY_XML
            elif xml_record is None:
                kind = RcvDifferenceType.ONLY_RCV
            elif rcv_entry.total_amount != xml_record.total:
                kind = RcvDifferenceType.TOTAL_MISMATCH
            else:
                kind = RcvDifferenceType.MATCH
            differences.append(
                RcvDifference(
                    kind=kind,
                    issuer_rut=identity[0],
                    document_type=identity[1],
                    folio=identity[2],
                    xml_total=xml_record.total if xml_record else None,
                    rcv_total=rcv_entry.total_amount if rcv_entry else None,
                )
            )
        return tuple(differences)
