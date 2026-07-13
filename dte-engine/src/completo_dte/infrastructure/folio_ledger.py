"""Ledger transaccional e idempotente para asignación de folios."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from completo_dte.domain import (
    TrustedCafAuthorization,
    normalize_rut,
)

from .document_ledger import DocumentLedgerMixin
from .ledger_codec import (
    _lease,
    _now,
    _required_token,
)
from .received_ledger import ReceivedLedgerMixin
from .records import (
    CafRangeExhausted,
    FolioLease,
    FolioLedgerError,
    LeaseState,
)
from .transmission_ledger import TransmissionLedgerMixin
from .monthly_close_ledger import MonthlyCloseLedgerMixin
from .payment_ledger import PaymentLedgerMixin
from .commercial_ledger import CommercialLedgerMixin
from .inventory_ledger import InventoryLedgerMixin
from .treasury_ledger import TreasuryLedgerMixin
from .recurring_ledger import RecurringLedgerMixin
from .collection_ledger import CollectionLedgerMixin


class FolioLedger(
    DocumentLedgerMixin,
    ReceivedLedgerMixin,
    TransmissionLedgerMixin,
    MonthlyCloseLedgerMixin,
    PaymentLedgerMixin,
    CommercialLedgerMixin,
    InventoryLedgerMixin,
    TreasuryLedgerMixin,
    RecurringLedgerMixin,
    CollectionLedgerMixin,
):
    def __init__(self, database: str | Path) -> None:
        self._database = str(database)

    def migrate(self) -> None:
        migrations = files("completo_dte.infrastructure").joinpath("migrations")
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL,
                    sha256 TEXT
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(schema_migrations)"
                ).fetchall()
            }
            if "sha256" not in columns:
                connection.execute(
                    "ALTER TABLE schema_migrations ADD COLUMN sha256 TEXT"
                )
            applied = {
                row["name"]: row["sha256"]
                for row in connection.execute(
                    "SELECT name, sha256 FROM schema_migrations"
                ).fetchall()
            }
            for migration in sorted(
                (item for item in migrations.iterdir() if item.name.endswith(".sql")),
                key=lambda item: item.name,
            ):
                source = migration.read_bytes()
                digest = hashlib.sha256(source).hexdigest()
                if migration.name in applied:
                    previous = applied[migration.name]
                    if previous is None:
                        connection.execute(
                            "UPDATE schema_migrations SET sha256 = ? WHERE name = ?",
                            (digest, migration.name),
                        )
                    elif previous != digest:
                        raise FolioLedgerError(
                            f"La migración aplicada {migration.name} cambió de contenido"
                        )
                    continue
                connection.executescript(source.decode("utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations (name, applied_at, sha256) VALUES (?, ?, ?)",
                    (migration.name, _now(), digest),
                )

    def import_caf(self, tenant_id: str, caf: TrustedCafAuthorization) -> str:
        _required_token(tenant_id, "tenant_id")
        if not isinstance(caf, TrustedCafAuthorization):
            raise FolioLedgerError("Sólo se pueden importar CAF autenticados")
        data = caf.data
        caf_id = hashlib.sha256(caf.caf_xml).hexdigest()
        now = _now()
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM caf_ranges WHERE id = ?",
                (caf_id,),
            ).fetchone()
            if existing is not None:
                if existing["tenant_id"] != tenant_id:
                    raise FolioLedgerError("El CAF ya está asociado a otro tenant")
                return caf_id

            overlap = connection.execute(
                """
                SELECT id FROM caf_ranges
                WHERE tenant_id = ? AND taxpayer_rut = ? AND document_type = ?
                  AND active = 1 AND NOT (folio_to < ? OR folio_from > ?)
                """,
                (
                    tenant_id,
                    data.issuer_rut,
                    data.document_type,
                    data.folio_from,
                    data.folio_to,
                ),
            ).fetchone()
            if overlap is not None:
                raise FolioLedgerError(
                    "El rango CAF se superpone con otro rango activo"
                )

            connection.execute(
                """
                INSERT INTO caf_ranges (
                    id, tenant_id, taxpayer_rut, document_type, folio_from,
                    folio_to, next_folio, key_id, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    caf_id,
                    tenant_id,
                    data.issuer_rut,
                    data.document_type,
                    data.folio_from,
                    data.folio_to,
                    data.folio_from,
                    data.key_id,
                    now,
                ),
            )
        return caf_id

    def reserve(
        self,
        *,
        tenant_id: str,
        taxpayer_rut: str,
        document_type: int,
        idempotency_key: str,
        request_sha256: str,
    ) -> FolioLease:
        _required_token(tenant_id, "tenant_id")
        _required_token(idempotency_key, "idempotency_key")
        if len(request_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in request_sha256.lower()
        ):
            raise FolioLedgerError(
                "request_sha256 debe ser un hash SHA-256 hexadecimal"
            )
        request_sha256 = request_sha256.lower()
        taxpayer_rut = normalize_rut(taxpayer_rut)
        now = _now()

        with self._transaction() as connection:
            existing = connection.execute(
                """
                SELECT * FROM folio_leases
                WHERE tenant_id = ? AND idempotency_key = ?
                """,
                (tenant_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if (
                    existing["taxpayer_rut"] != taxpayer_rut
                    or existing["document_type"] != document_type
                    or existing["request_sha256"] != request_sha256
                ):
                    raise FolioLedgerError(
                        "La idempotency key ya fue usada con un payload diferente"
                    )
                return _lease(existing)

            caf_range = connection.execute(
                """
                SELECT * FROM caf_ranges
                WHERE tenant_id = ? AND taxpayer_rut = ? AND document_type = ?
                  AND active = 1 AND next_folio <= folio_to
                ORDER BY folio_from, imported_at
                LIMIT 1
                """,
                (tenant_id, taxpayer_rut, document_type),
            ).fetchone()
            if caf_range is None:
                raise CafRangeExhausted("No quedan folios CAF disponibles")

            folio = caf_range["next_folio"]
            updated = connection.execute(
                """
                UPDATE caf_ranges SET next_folio = next_folio + 1
                WHERE id = ? AND next_folio = ?
                """,
                (caf_range["id"], folio),
            )
            if updated.rowcount != 1:
                raise FolioLedgerError("Conflicto al avanzar el rango CAF")

            lease_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO folio_leases (
                    id, tenant_id, taxpayer_rut, document_type, folio,
                    caf_range_id, idempotency_key, request_sha256, status,
                    reserved_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'reserved', ?, ?)
                """,
                (
                    lease_id,
                    tenant_id,
                    taxpayer_rut,
                    document_type,
                    folio,
                    caf_range["id"],
                    idempotency_key,
                    request_sha256,
                    now,
                    now,
                ),
            )
            self._event(connection, lease_id, LeaseState.RESERVED, now)
            row = connection.execute(
                "SELECT * FROM folio_leases WHERE id = ?",
                (lease_id,),
            ).fetchone()
            return _lease(row)

    def consume(self, lease_id: str, document_id: str) -> FolioLease:
        _required_token(document_id, "document_id")
        return self._transition(
            lease_id,
            LeaseState.CONSUMED,
            document_id=document_id,
        )

    def void(self, lease_id: str, reason: str) -> FolioLease:
        _required_token(reason, "reason")
        return self._transition(
            lease_id,
            LeaseState.VOIDED,
            void_reason=reason,
        )

    def events(self, lease_id: str) -> tuple[dict, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT sequence, event_type, occurred_at, metadata
                FROM folio_events WHERE lease_id = ? ORDER BY sequence
                """,
                (lease_id,),
            ).fetchall()
        return tuple(
            {
                "sequence": row["sequence"],
                "event_type": row["event_type"],
                "occurred_at": row["occurred_at"],
                "metadata": json.loads(row["metadata"]),
            }
            for row in rows
        )

    def _transition(
        self,
        lease_id: str,
        target: LeaseState,
        *,
        document_id: str | None = None,
        void_reason: str | None = None,
    ) -> FolioLease:
        now = _now()
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM folio_leases WHERE id = ?",
                (lease_id,),
            ).fetchone()
            if row is None:
                raise FolioLedgerError("La reserva de folio no existe")
            current = _lease(row)
            if current.status == target:
                same_payload = (
                    target == LeaseState.CONSUMED and current.document_id == document_id
                ) or (
                    target == LeaseState.VOIDED and current.void_reason == void_reason
                )
                if same_payload:
                    return current
            if current.status != LeaseState.RESERVED:
                raise FolioLedgerError(
                    f"No se puede pasar una reserva {current.status} a {target}"
                )

            connection.execute(
                """
                UPDATE folio_leases
                SET status = ?, document_id = ?, void_reason = ?, updated_at = ?
                WHERE id = ? AND status = 'reserved'
                """,
                (target.value, document_id, void_reason, now, lease_id),
            )
            metadata = (
                {"document_id": document_id} if document_id else {"reason": void_reason}
            )
            self._event(connection, lease_id, target, now, metadata)
            updated = connection.execute(
                "SELECT * FROM folio_leases WHERE id = ?",
                (lease_id,),
            ).fetchone()
            return _lease(updated)

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        lease_id: str,
        event_type: LeaseState,
        occurred_at: str,
        metadata: dict | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO folio_events (lease_id, event_type, occurred_at, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (
                lease_id,
                event_type.value,
                occurred_at,
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _transaction(self):
        return _ImmediateTransaction(self._connect())


class _ImmediateTransaction:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def __enter__(self) -> sqlite3.Connection:
        self.connection.execute("BEGIN IMMEDIATE")
        return self.connection

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            self.connection.execute("COMMIT" if exc_type is None else "ROLLBACK")
        finally:
            self.connection.close()
