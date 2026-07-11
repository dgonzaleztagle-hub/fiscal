"""Snapshots RCV inmutables e independientes del formato del conector."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from completo_dte.domain import RcvPeriod, RcvPurchaseEntry, RcvPurchaseStatus
from .folio_ledger import FolioLedgerError


@dataclass(frozen=True)
class RcvSnapshotRecord:
    id: str
    tenant_id: str
    period: str
    version: int
    source: str
    payload_sha256: str
    imported_at: str


@dataclass(frozen=True)
class RcvEntryRecord:
    id: str
    snapshot_id: str
    entry: RcvPurchaseEntry


class RcvRepository:
    def __init__(self, database: str | Path) -> None:
        self._database = str(database)

    def import_snapshot(
        self,
        *,
        tenant_id: str,
        period: RcvPeriod,
        entries: tuple[RcvPurchaseEntry, ...],
        source: str,
    ) -> RcvSnapshotRecord:
        if source not in {"official_connector", "csv_import", "synthetic"}:
            raise FolioLedgerError("Fuente RCV inválida")
        identities = [entry.identity for entry in entries]
        if len(set(identities)) != len(identities):
            raise FolioLedgerError("El snapshot RCV contiene documentos duplicados")
        payload_hash = _entries_hash(entries)
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT * FROM rcv_purchase_snapshots
                   WHERE tenant_id=? AND period=? AND payload_sha256=?""",
                (tenant_id, period.key, payload_hash),
            ).fetchone()
            if existing is not None:
                connection.execute("COMMIT")
                return _snapshot(existing)
            version = connection.execute(
                "SELECT COUNT(*) FROM rcv_purchase_snapshots WHERE tenant_id=? AND period=?",
                (tenant_id, period.key),
            ).fetchone()[0] + 1
            snapshot_id = str(uuid4())
            connection.execute(
                """INSERT INTO rcv_purchase_snapshots
                   (id,tenant_id,period,version,source,payload_sha256,imported_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (snapshot_id, tenant_id, period.key, version, source, payload_hash, now),
            )
            for entry in entries:
                connection.execute(
                    """INSERT INTO rcv_purchase_entries
                       (id,snapshot_id,issuer_rut,document_type,folio,issued_on,
                        exempt_amount,net_amount,vat_amount,total_amount,status)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        str(uuid4()), snapshot_id, entry.issuer_rut,
                        int(entry.document_type), entry.folio, entry.issued_on.isoformat(),
                        entry.exempt_amount, entry.net_amount, entry.vat_amount,
                        entry.total_amount, entry.status.value,
                    ),
                )
            connection.execute("COMMIT")
            row = connection.execute(
                "SELECT * FROM rcv_purchase_snapshots WHERE id=?", (snapshot_id,)
            ).fetchone()
            return _snapshot(row)
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def latest_snapshot(self, *, tenant_id: str, period: RcvPeriod) -> RcvSnapshotRecord | None:
        connection = self._connect()
        try:
            row = connection.execute(
                """SELECT * FROM rcv_purchase_snapshots
                   WHERE tenant_id=? AND period=? ORDER BY version DESC LIMIT 1""",
                (tenant_id, period.key),
            ).fetchone()
            return _snapshot(row) if row is not None else None
        finally:
            connection.close()

    def entries(self, snapshot_id: str, *, tenant_id: str) -> list[RcvEntryRecord]:
        connection = self._connect()
        try:
            rows = connection.execute(
                """SELECT e.* FROM rcv_purchase_entries e
                   JOIN rcv_purchase_snapshots s ON s.id=e.snapshot_id
                   WHERE e.snapshot_id=? AND s.tenant_id=?
                   ORDER BY e.issued_on, e.document_type, e.folio""",
                (snapshot_id, tenant_id),
            ).fetchall()
            return [_entry(row) for row in rows]
        finally:
            connection.close()

    def _connect(self):
        connection = sqlite3.connect(self._database, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection


def _entries_hash(entries: tuple[RcvPurchaseEntry, ...]) -> str:
    payload = [
        {
            "issuer_rut": entry.issuer_rut,
            "document_type": int(entry.document_type),
            "folio": entry.folio,
            "issued_on": entry.issued_on.isoformat(),
            "exempt": entry.exempt_amount,
            "net": entry.net_amount,
            "vat": entry.vat_amount,
            "total": entry.total_amount,
            "status": entry.status.value,
        }
        for entry in sorted(entries, key=lambda value: value.identity)
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _snapshot(row) -> RcvSnapshotRecord:
    return RcvSnapshotRecord(**dict(row))


def _entry(row) -> RcvEntryRecord:
    from datetime import date
    from completo_dte.domain import DocumentType

    return RcvEntryRecord(
        id=row["id"],
        snapshot_id=row["snapshot_id"],
        entry=RcvPurchaseEntry(
            issuer_rut=row["issuer_rut"],
            document_type=DocumentType(row["document_type"]),
            folio=row["folio"],
            issued_on=date.fromisoformat(row["issued_on"]),
            exempt_amount=row["exempt_amount"],
            net_amount=row["net_amount"],
            vat_amount=row["vat_amount"],
            total_amount=row["total_amount"],
            status=RcvPurchaseStatus(row["status"]),
        ),
    )
