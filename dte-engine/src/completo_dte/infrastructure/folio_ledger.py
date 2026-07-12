"""Ledger transaccional e idempotente para asignación de folios."""

from datetime import datetime, timezone
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from uuid import uuid4

from lxml import etree

from completo_dte.domain import (
    PurchaseLineAllocation,
    ReceivedDocument,
    TrustedCafAuthorization,
    normalize_rut,
)
from .records import (
    AttemptState,
    CafRangeExhausted,
    DeliveryState,
    EnvelopeState,
    FiscalDeliveryRecord,
    FiscalDocumentRecord,
    FiscalEnvelopeRecord,
    FolioLease,
    FolioLedgerError,
    LeaseState,
    ReceivedClassificationRecord,
    ReceivedDecisionAttemptRecord,
    ReceivedDecisionRecord,
    ReceivedDecisionState,
    ReceivedFiscalDocumentRecord,
    ReceivedLineAllocationRecord,
    ReceivedLineRecord,
    ReceivedSiiObservationRecord,
    SubmissionAttemptRecord,
)


class FolioLedger:
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
                connection.execute("ALTER TABLE schema_migrations ADD COLUMN sha256 TEXT")
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
                raise FolioLedgerError("El rango CAF se superpone con otro rango activo")

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
            raise FolioLedgerError("request_sha256 debe ser un hash SHA-256 hexadecimal")
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

    def persist_signed_document(
        self,
        lease_id: str,
        *,
        document_id: str,
        signed_xml: bytes,
        corrects_record_id: str | None = None,
        correction_code: int | None = None,
    ) -> FiscalDocumentRecord:
        _required_token(document_id, "document_id")
        if not signed_xml:
            raise FolioLedgerError("El XML firmado no puede estar vacío")
        if (corrects_record_id is None) != (correction_code is None):
            raise FolioLedgerError("Documento corregido y código deben informarse juntos")
        now = _now()
        with self._transaction() as connection:
            lease_row = connection.execute(
                "SELECT * FROM folio_leases WHERE id = ?",
                (lease_id,),
            ).fetchone()
            if lease_row is None:
                raise FolioLedgerError("La reserva de folio no existe")
            lease = _lease(lease_row)

            existing = connection.execute(
                "SELECT * FROM fiscal_documents WHERE lease_id = ?",
                (lease_id,),
            ).fetchone()
            if existing is not None:
                if lease.status != LeaseState.CONSUMED:
                    raise FolioLedgerError("Documento persistido con folio no consumido")
                return _document(existing)

            if lease.status != LeaseState.RESERVED:
                raise FolioLedgerError(
                    f"No se puede persistir un documento con reserva {lease.status}"
                )
            expected_id = f"F{lease.folio}T{lease.document_type}"
            if document_id != expected_id:
                raise FolioLedgerError(
                    f"El ID fiscal debe ser {expected_id} para la reserva asignada"
                )

            target = None
            applied_amount = 0
            if corrects_record_id is not None:
                if lease.document_type not in {56, 61} or correction_code not in {1, 2, 3}:
                    raise FolioLedgerError("La relación de corrección no corresponde a la reserva")
                target_row = connection.execute(
                    "SELECT * FROM fiscal_documents WHERE id = ?",
                    (corrects_record_id,),
                ).fetchone()
                if target_row is None:
                    raise FolioLedgerError("El documento original no existe")
                target = _document(target_row)
                if target.tenant_id != lease.tenant_id or target.taxpayer_rut != lease.taxpayer_rut:
                    raise FolioLedgerError("No se puede corregir un documento de otro tenant o emisor")
                if correction_code == 3 and target.document_type not in {33, 34}:
                    raise FolioLedgerError("La corrección de montos requiere factura original 33/34")
                applied_amount = _xml_total(signed_xml)
                if lease.document_type == 61 and correction_code in {1, 3}:
                    original_total = _xml_total(target.signed_xml)
                    credited = connection.execute(
                        """
                        SELECT COALESCE(SUM(c.applied_amount), 0) AS amount
                        FROM fiscal_document_corrections c
                        JOIN fiscal_documents source ON source.id = c.source_document_id
                        WHERE c.target_document_id = ? AND source.document_type = 61
                          AND c.correction_code IN (1, 3)
                        """,
                        (target.id,),
                    ).fetchone()["amount"]
                    if applied_amount > original_total - int(credited):
                        raise FolioLedgerError("La nota de crédito supera el saldo vigente")

            record_id = str(uuid4())
            public_id = uuid4().hex
            digest = hashlib.sha256(signed_xml).hexdigest()
            connection.execute(
                """
                INSERT INTO fiscal_documents (
                    id, lease_id, tenant_id, taxpayer_rut, document_type,
                    folio, document_id, xml_sha256, signed_xml, created_at, public_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    lease.id,
                    lease.tenant_id,
                    lease.taxpayer_rut,
                    lease.document_type,
                    lease.folio,
                    document_id,
                    digest,
                    signed_xml,
                    now,
                    public_id,
                ),
            )
            updated = connection.execute(
                """
                UPDATE folio_leases
                SET status = 'consumed', document_id = ?, updated_at = ?
                WHERE id = ? AND status = 'reserved'
                """,
                (document_id, now, lease.id),
            )
            if updated.rowcount != 1:
                raise FolioLedgerError("No fue posible consumir atómicamente el folio")
            self._event(
                connection,
                lease.id,
                LeaseState.CONSUMED,
                now,
                {"document_id": document_id, "xml_sha256": digest},
            )
            if target is not None:
                connection.execute(
                    """
                    INSERT INTO fiscal_document_corrections (
                        source_document_id, target_document_id, correction_code,
                        applied_amount, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (record_id, target.id, correction_code, applied_amount, now),
                )
            row = connection.execute(
                "SELECT * FROM fiscal_documents WHERE id = ?",
                (record_id,),
            ).fetchone()
            return _document(row)

    def corrections_for(
        self,
        record_id: str,
        *,
        tenant_id: str,
    ) -> tuple[dict[str, object], ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT source.id AS source_record_id, source.document_id,
                       source.document_type, c.correction_code, c.applied_amount,
                       c.created_at
                FROM fiscal_document_corrections c
                JOIN fiscal_documents source ON source.id = c.source_document_id
                JOIN fiscal_documents target ON target.id = c.target_document_id
                WHERE c.target_document_id = ? AND target.tenant_id = ?
                ORDER BY c.created_at, source.id
                """,
                (record_id, tenant_id),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def document_by_lease(self, lease_id: str) -> FiscalDocumentRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM fiscal_documents WHERE lease_id = ?",
                (lease_id,),
            ).fetchone()
        return _document(row) if row is not None else None

    def document_by_id(
        self,
        record_id: str,
        *,
        tenant_id: str,
    ) -> FiscalDocumentRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM fiscal_documents
                WHERE id = ? AND tenant_id = ?
                """,
                (record_id, tenant_id),
            ).fetchone()
        return _document(row) if row is not None else None

    def document_by_public_id(self, public_id: str) -> FiscalDocumentRecord | None:
        if len(public_id) != 32 or any(
            character not in "0123456789abcdef" for character in public_id.lower()
        ):
            return None
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM fiscal_documents WHERE public_id = ?",
                (public_id.lower(),),
            ).fetchone()
        return _document(row) if row is not None else None

    def list_documents(
        self,
        *,
        tenant_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[FiscalDocumentRecord, ...]:
        _required_token(tenant_id, "tenant_id")
        if not 1 <= limit <= 200:
            raise FolioLedgerError("limit debe estar entre 1 y 200")
        if offset < 0:
            raise FolioLedgerError("offset no puede ser negativo")
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM fiscal_documents
                WHERE tenant_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (tenant_id, limit, offset),
            ).fetchall()
        return tuple(_document(row) for row in rows)

    def pending_envelope_documents(
        self,
        *,
        tenant_id: str,
        taxpayer_rut: str,
        relation_kind: str,
        limit: int = 500,
        document_types: tuple[int, ...] = (39, 41),
    ) -> tuple[FiscalDocumentRecord, ...]:
        _required_token(tenant_id, "tenant_id")
        taxpayer_rut = normalize_rut(taxpayer_rut)
        if relation_kind not in {"dispatch", "consumption"}:
            raise FolioLedgerError("Relación documental no soportada")
        if not 1 <= limit <= 10_000:
            raise FolioLedgerError("limit debe estar entre 1 y 10000")
        if (
            not document_types
            or len(document_types) != len(set(document_types))
            or any(value not in {33, 34, 39, 41, 52, 56, 61} for value in document_types)
        ):
            raise FolioLedgerError("Tipos documentales pendientes no soportados")
        type_placeholders = ",".join("?" for _ in document_types)
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT d.* FROM fiscal_documents d
                WHERE d.tenant_id = ? AND d.taxpayer_rut = ?
                  AND d.document_type IN ({type_placeholders})
                  AND NOT EXISTS (
                    SELECT 1 FROM fiscal_envelope_documents ed
                    WHERE ed.document_record_id = d.id
                      AND ed.relation_kind = ?
                  )
                ORDER BY d.created_at, d.document_type, d.folio
                LIMIT ?
                """,  # noqa: S608 - sólo placeholders; valores parametrizados.
                (tenant_id, taxpayer_rut, *document_types, relation_kind, limit),
            ).fetchall()
        return tuple(_document(row) for row in rows)

    def persist_envelope_with_documents(
        self,
        *,
        tenant_id: str,
        taxpayer_rut: str,
        kind: str,
        document_id: str,
        signed_xml: bytes,
        document_record_ids: tuple[str, ...],
    ) -> FiscalEnvelopeRecord:
        """Persiste sobre y pertenencia documental en una transacción."""
        _required_token(tenant_id, "tenant_id")
        _required_token(document_id, "document_id")
        taxpayer_rut = normalize_rut(taxpayer_rut)
        relation_kind = {
            "envio_boleta": "dispatch",
            "envio_dte": "dispatch",
            "rcof": "consumption",
        }.get(kind)
        if relation_kind is None:
            raise FolioLedgerError("Tipo de sobre no soportado")
        if not signed_xml:
            raise FolioLedgerError("El XML del sobre no puede estar vacío")
        if not document_record_ids or len(document_record_ids) != len(set(document_record_ids)):
            raise FolioLedgerError("El sobre necesita documentos únicos")
        if kind in {"envio_boleta", "envio_dte"} and len(document_record_ids) > 500:
            raise FolioLedgerError("El sobre no puede superar 500 documentos")
        digest = hashlib.sha256(signed_xml).hexdigest()
        now = _now()
        with self._transaction() as connection:
            existing = connection.execute(
                """
                SELECT * FROM fiscal_envelopes
                WHERE tenant_id = ? AND taxpayer_rut = ? AND kind = ? AND document_id = ?
                """,
                (tenant_id, taxpayer_rut, kind, document_id),
            ).fetchone()
            if existing is not None:
                envelope = _envelope(existing)
                linked = connection.execute(
                    """
                    SELECT document_record_id FROM fiscal_envelope_documents
                    WHERE envelope_id = ? AND relation_kind = ? ORDER BY position
                    """,
                    (envelope.id, relation_kind),
                ).fetchall()
                linked_ids = tuple(row["document_record_id"] for row in linked)
                if (
                    envelope.xml_sha256 != digest
                    or envelope.signed_xml != signed_xml
                    or linked_ids != document_record_ids
                ):
                    raise FolioLedgerError("El ID del sobre ya existe con contenido diferente")
                return envelope

            placeholders = ",".join("?" for _ in document_record_ids)
            rows = connection.execute(
                f"SELECT * FROM fiscal_documents WHERE id IN ({placeholders})",  # noqa: S608
                document_record_ids,
            ).fetchall()
            records = {row["id"]: _document(row) for row in rows}
            if len(records) != len(document_record_ids):
                raise FolioLedgerError("Algún documento del sobre no existe")
            for record_id in document_record_ids:
                record = records[record_id]
                if record.tenant_id != tenant_id or record.taxpayer_rut != taxpayer_rut:
                    raise FolioLedgerError("El sobre contiene documentos de otro tenant o emisor")
                allowed_types = {
                    "envio_boleta": {39, 41},
                    "envio_dte": {33, 34},
                    "rcof": {39, 41},
                }[kind]
                if record.document_type not in allowed_types:
                    raise FolioLedgerError("El sobre contiene un tipo documental inválido")
            claimed = connection.execute(
                f"""
                SELECT document_record_id FROM fiscal_envelope_documents
                WHERE relation_kind = ? AND document_record_id IN ({placeholders})
                """,  # noqa: S608 - sólo placeholders; valores parametrizados.
                (relation_kind, *document_record_ids),
            ).fetchall()
            if claimed:
                raise FolioLedgerError("Un documento ya pertenece a otro sobre del mismo rol")

            envelope_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO fiscal_envelopes (
                    id, tenant_id, taxpayer_rut, kind, document_id, xml_sha256,
                    signed_xml, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'prepared', ?, ?)
                """,
                (
                    envelope_id, tenant_id, taxpayer_rut, kind, document_id,
                    digest, signed_xml, now, now,
                ),
            )
            connection.executemany(
                """
                INSERT INTO fiscal_envelope_documents (
                    envelope_id, document_record_id, relation_kind, position, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (envelope_id, record_id, relation_kind, position, now)
                    for position, record_id in enumerate(document_record_ids, 1)
                ),
            )
            row = connection.execute(
                "SELECT * FROM fiscal_envelopes WHERE id = ?",
                (envelope_id,),
            ).fetchone()
            return _envelope(row)

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

    def persist_envelope(
        self,
        *,
        tenant_id: str,
        taxpayer_rut: str,
        kind: str,
        document_id: str,
        signed_xml: bytes,
    ) -> FiscalEnvelopeRecord:
        _required_token(tenant_id, "tenant_id")
        _required_token(document_id, "document_id")
        taxpayer_rut = normalize_rut(taxpayer_rut)
        if kind not in ("envio_boleta", "envio_dte", "rcof"):
            raise FolioLedgerError("Tipo de sobre no soportado")
        if not signed_xml:
            raise FolioLedgerError("El XML del sobre no puede estar vacío")
        digest = hashlib.sha256(signed_xml).hexdigest()
        now = _now()
        with self._transaction() as connection:
            existing = connection.execute(
                """
                SELECT * FROM fiscal_envelopes
                WHERE tenant_id = ? AND taxpayer_rut = ? AND kind = ? AND document_id = ?
                """,
                (tenant_id, taxpayer_rut, kind, document_id),
            ).fetchone()
            if existing is not None:
                record = _envelope(existing)
                if record.xml_sha256 != digest or record.signed_xml != signed_xml:
                    raise FolioLedgerError(
                        "El ID del sobre ya existe con contenido diferente"
                    )
                return record
            envelope_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO fiscal_envelopes (
                    id, tenant_id, taxpayer_rut, kind, document_id, xml_sha256,
                    signed_xml, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'prepared', ?, ?)
                """,
                (
                    envelope_id,
                    tenant_id,
                    taxpayer_rut,
                    kind,
                    document_id,
                    digest,
                    signed_xml,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM fiscal_envelopes WHERE id = ?",
                (envelope_id,),
            ).fetchone()
            return _envelope(row)

    def envelope_by_id(
        self,
        envelope_id: str,
        *,
        tenant_id: str,
    ) -> FiscalEnvelopeRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM fiscal_envelopes WHERE id = ? AND tenant_id = ?",
                (envelope_id, tenant_id),
            ).fetchone()
        return _envelope(row) if row is not None else None

    def list_envelopes(
        self,
        *,
        tenant_id: str,
        limit: int = 100,
    ) -> tuple[FiscalEnvelopeRecord, ...]:
        _required_token(tenant_id, "tenant_id")
        if not 1 <= limit <= 500:
            raise FolioLedgerError("limit debe estar entre 1 y 500")
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM fiscal_envelopes WHERE tenant_id = ?
                ORDER BY created_at DESC, id DESC LIMIT ?
                """,
                (tenant_id, limit),
            ).fetchall()
        return tuple(_envelope(row) for row in rows)

    def operational_alerts(
        self,
        *,
        tenant_id: str,
        low_caf_threshold: int = 20,
    ) -> tuple[dict[str, object], ...]:
        _required_token(tenant_id, "tenant_id")
        if low_caf_threshold < 0:
            raise FolioLedgerError("El umbral CAF no puede ser negativo")
        alerts: list[dict[str, object]] = []
        with self._connection() as connection:
            caf_rows = connection.execute(
                """
                SELECT taxpayer_rut, document_type,
                       MAX(0, folio_to - next_folio + 1) AS remaining
                FROM caf_ranges WHERE tenant_id = ? AND active = 1
                ORDER BY taxpayer_rut, document_type
                """,
                (tenant_id,),
            ).fetchall()
            unknown_rows = connection.execute(
                """
                SELECT id, kind, document_id FROM fiscal_envelopes
                WHERE tenant_id = ? AND status = 'unknown'
                ORDER BY created_at
                """,
                (tenant_id,),
            ).fetchall()
            pending_consumption = connection.execute(
                """
                SELECT COUNT(*) AS count FROM fiscal_documents d
                WHERE d.tenant_id = ? AND d.document_type IN (39, 41)
                  AND NOT EXISTS (
                    SELECT 1 FROM fiscal_envelope_documents ed
                    WHERE ed.document_record_id = d.id
                      AND ed.relation_kind = 'consumption'
                  )
                """,
                (tenant_id,),
            ).fetchone()["count"]
        for row in caf_rows:
            remaining = int(row["remaining"])
            if remaining <= low_caf_threshold:
                alerts.append({
                    "code": "caf_exhausted" if remaining == 0 else "caf_low",
                    "severity": "critical" if remaining == 0 else "warning",
                    "message": (
                        f"CAF tipo {row['document_type']} con {remaining} folios disponibles"
                    ),
                    "resource_id": f"{row['taxpayer_rut']}:{row['document_type']}",
                })
        for row in unknown_rows:
            alerts.append({
                "code": "envelope_unknown",
                "severity": "critical",
                "message": f"{row['kind']} {row['document_id']} requiere conciliación",
                "resource_id": row["id"],
            })
        if pending_consumption:
            alerts.append({
                "code": "rcof_pending",
                "severity": "warning",
                "message": f"{pending_consumption} boletas aún no están incluidas en RCOF",
                "resource_id": None,
            })
        return tuple(alerts)

    def queue_delivery(
        self,
        *,
        tenant_id: str,
        document_record_id: str,
        recipient_email: str,
        exchange_xml: bytes,
        pdf: bytes,
    ) -> FiscalDeliveryRecord:
        _required_token(tenant_id, "tenant_id")
        recipient_email = recipient_email.strip().lower()
        if (
            not recipient_email
            or len(recipient_email) > 254
            or recipient_email.count("@") != 1
            or any(character.isspace() for character in recipient_email)
        ):
            raise FolioLedgerError("Correo de entrega inválido")
        if not exchange_xml or not pdf:
            raise FolioLedgerError("La entrega requiere XML de intercambio y PDF")
        xml_digest = hashlib.sha256(exchange_xml).hexdigest()
        pdf_digest = hashlib.sha256(pdf).hexdigest()
        now = _now()
        with self._transaction() as connection:
            document = connection.execute(
                "SELECT tenant_id, document_type FROM fiscal_documents WHERE id = ?",
                (document_record_id,),
            ).fetchone()
            if document is None or document["tenant_id"] != tenant_id:
                raise FolioLedgerError("El documento no existe para el tenant")
            if document["document_type"] not in {33, 34}:
                raise FolioLedgerError("Sólo las facturas admiten intercambio por esta vía")
            existing = connection.execute(
                """
                SELECT * FROM fiscal_deliveries
                WHERE document_record_id = ? AND recipient_email = ?
                  AND kind = 'invoice_exchange'
                """,
                (document_record_id, recipient_email),
            ).fetchone()
            if existing is not None:
                delivery = _delivery(existing)
                if delivery.exchange_xml != exchange_xml or delivery.pdf != pdf:
                    raise FolioLedgerError("La entrega ya existe con artefactos diferentes")
                return delivery
            delivery_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO fiscal_deliveries (
                    id, tenant_id, document_record_id, recipient_email, kind,
                    exchange_xml_sha256, exchange_xml, pdf_sha256, pdf,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'invoice_exchange', ?, ?, ?, ?, 'queued', ?, ?)
                """,
                (
                    delivery_id, tenant_id, document_record_id, recipient_email,
                    xml_digest, exchange_xml, pdf_digest, pdf, now, now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM fiscal_deliveries WHERE id = ?",
                (delivery_id,),
            ).fetchone()
            return _delivery(row)

    def delivery_by_id(
        self,
        delivery_id: str,
        *,
        tenant_id: str,
    ) -> FiscalDeliveryRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM fiscal_deliveries WHERE id = ? AND tenant_id = ?",
                (delivery_id, tenant_id),
            ).fetchone()
        return _delivery(row) if row is not None else None

    def begin_delivery(self, delivery_id: str, *, tenant_id: str) -> FiscalDeliveryRecord:
        now = _now()
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM fiscal_deliveries WHERE id = ? AND tenant_id = ?",
                (delivery_id, tenant_id),
            ).fetchone()
            if row is None:
                raise FolioLedgerError("La entrega no existe para el tenant")
            delivery = _delivery(row)
            if delivery.status is DeliveryState.SENT:
                raise FolioLedgerError("La entrega ya fue enviada y no debe repetirse")
            if delivery.status is DeliveryState.UNKNOWN:
                raise FolioLedgerError("La entrega ambigua debe conciliarse, no reenviarse")
            if delivery.status is DeliveryState.SENDING:
                raise FolioLedgerError("La entrega ya está en curso")
            connection.execute(
                """
                UPDATE fiscal_deliveries
                SET status = 'sending', attempt_count = attempt_count + 1,
                    error_message = NULL, updated_at = ? WHERE id = ?
                """,
                (now, delivery_id),
            )
            updated = connection.execute(
                "SELECT * FROM fiscal_deliveries WHERE id = ?",
                (delivery_id,),
            ).fetchone()
            return _delivery(updated)

    def complete_delivery(
        self,
        delivery_id: str,
        *,
        status: DeliveryState,
        provider_id: str | None = None,
        error_message: str | None = None,
    ) -> FiscalDeliveryRecord:
        if status not in {DeliveryState.SENT, DeliveryState.FAILED, DeliveryState.UNKNOWN}:
            raise FolioLedgerError("Estado final de entrega inválido")
        now = _now()
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM fiscal_deliveries WHERE id = ?",
                (delivery_id,),
            ).fetchone()
            if row is None:
                raise FolioLedgerError("La entrega no existe")
            if _delivery(row).status is not DeliveryState.SENDING:
                raise FolioLedgerError("La entrega no estaba en curso")
            connection.execute(
                """
                UPDATE fiscal_deliveries
                SET status = ?, provider_id = ?, error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (status.value, provider_id, error_message, now, delivery_id),
            )
            updated = connection.execute(
                "SELECT * FROM fiscal_deliveries WHERE id = ?",
                (delivery_id,),
            ).fetchone()
            return _delivery(updated)

    def begin_submission(self, envelope_id: str) -> SubmissionAttemptRecord:
        now = _now()
        with self._transaction() as connection:
            envelope_row = connection.execute(
                "SELECT * FROM fiscal_envelopes WHERE id = ?",
                (envelope_id,),
            ).fetchone()
            if envelope_row is None:
                raise FolioLedgerError("El sobre no existe")
            envelope = _envelope(envelope_row)
            if envelope.status in (
                EnvelopeState.SUBMITTED,
                EnvelopeState.ACCEPTED,
                EnvelopeState.ACCEPTED_WITH_OBJECTIONS,
            ):
                raise FolioLedgerError("El sobre ya tiene Track ID y no debe reenviarse")
            if envelope.status == EnvelopeState.UNKNOWN:
                raise FolioLedgerError(
                    "El resultado del envío es desconocido; debe reconciliarse antes de reintentar"
                )
            active = connection.execute(
                """
                SELECT * FROM fiscal_submission_attempts
                WHERE envelope_id = ? AND status = 'started'
                ORDER BY attempt_number DESC LIMIT 1
                """,
                (envelope_id,),
            ).fetchone()
            if active is not None:
                return _attempt(active)
            number = connection.execute(
                """
                SELECT COALESCE(MAX(attempt_number), 0) + 1 AS next
                FROM fiscal_submission_attempts WHERE envelope_id = ?
                """,
                (envelope_id,),
            ).fetchone()["next"]
            attempt_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO fiscal_submission_attempts (
                    id, envelope_id, attempt_number, status, request_sha256, started_at
                ) VALUES (?, ?, ?, 'started', ?, ?)
                """,
                (attempt_id, envelope_id, number, envelope.xml_sha256, now),
            )
            connection.execute(
                """
                UPDATE fiscal_envelopes
                SET status = 'submitting', updated_at = ?
                WHERE id = ?
                """,
                (now, envelope_id),
            )
            row = connection.execute(
                "SELECT * FROM fiscal_submission_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            return _attempt(row)

    def complete_submission(
        self,
        attempt_id: str,
        *,
        status: AttemptState,
        track_id: str | None = None,
        response_code: str | None = None,
        response_message: str | None = None,
    ) -> FiscalEnvelopeRecord:
        if status == AttemptState.STARTED:
            raise FolioLedgerError("El intento debe terminar en un estado final")
        if status == AttemptState.SUCCEEDED and not track_id:
            raise FolioLedgerError("Un envío exitoso debe incluir Track ID")
        now = _now()
        with self._transaction() as connection:
            attempt_row = connection.execute(
                "SELECT * FROM fiscal_submission_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            if attempt_row is None:
                raise FolioLedgerError("El intento de envío no existe")
            attempt = _attempt(attempt_row)
            if attempt.status != AttemptState.STARTED:
                envelope_row = connection.execute(
                    "SELECT * FROM fiscal_envelopes WHERE id = ?",
                    (attempt.envelope_id,),
                ).fetchone()
                return _envelope(envelope_row)
            connection.execute(
                """
                UPDATE fiscal_submission_attempts
                SET status = ?, track_id = ?, response_code = ?,
                    response_message = ?, completed_at = ?
                WHERE id = ? AND status = 'started'
                """,
                (
                    status.value,
                    track_id,
                    response_code,
                    response_message,
                    now,
                    attempt_id,
                ),
            )
            envelope_state = {
                AttemptState.SUCCEEDED: EnvelopeState.SUBMITTED,
                AttemptState.FAILED: EnvelopeState.PREPARED,
                AttemptState.UNKNOWN: EnvelopeState.UNKNOWN,
            }[status]
            connection.execute(
                """
                UPDATE fiscal_envelopes
                SET status = ?, track_id = COALESCE(?, track_id),
                    remote_code = ?, remote_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    envelope_state.value,
                    track_id,
                    response_code,
                    response_message,
                    now,
                    attempt.envelope_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM fiscal_envelopes WHERE id = ?",
                (attempt.envelope_id,),
            ).fetchone()
            return _envelope(row)

    def update_remote_state(
        self,
        envelope_id: str,
        *,
        status: EnvelopeState,
        remote_code: str | None = None,
        remote_message: str | None = None,
    ) -> FiscalEnvelopeRecord:
        if status not in (
            EnvelopeState.SUBMITTED,
            EnvelopeState.ACCEPTED,
            EnvelopeState.ACCEPTED_WITH_OBJECTIONS,
            EnvelopeState.REJECTED,
            EnvelopeState.UNKNOWN,
        ):
            raise FolioLedgerError("Estado remoto inválido")
        now = _now()
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM fiscal_envelopes WHERE id = ?",
                (envelope_id,),
            ).fetchone()
            if row is None:
                raise FolioLedgerError("El sobre no existe")
            envelope = _envelope(row)
            if not envelope.track_id:
                raise FolioLedgerError("No se puede conciliar un sobre sin Track ID")
            connection.execute(
                """
                UPDATE fiscal_envelopes
                SET status = ?, remote_code = ?, remote_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (status.value, remote_code, remote_message, now, envelope_id),
            )
            updated = connection.execute(
                "SELECT * FROM fiscal_envelopes WHERE id = ?",
                (envelope_id,),
            ).fetchone()
            return _envelope(updated)

    def import_received_document(
        self,
        *,
        tenant_id: str,
        document: ReceivedDocument,
        source: str,
        sii_received_at: str | None = None,
    ) -> ReceivedFiscalDocumentRecord:
        _required_token(tenant_id, "tenant_id")
        if source not in {"upload", "email", "official_connector"}:
            raise FolioLedgerError("Fuente de recepción inválida")
        now = _now()
        with self._transaction() as connection:
            existing = connection.execute(
                """
                SELECT * FROM received_fiscal_documents
                WHERE tenant_id = ? AND issuer_rut = ? AND document_type = ? AND folio = ?
                """,
                (
                    tenant_id,
                    document.issuer_rut,
                    int(document.document_type),
                    document.folio,
                ),
            ).fetchone()
            if existing is not None:
                record = _received_document(existing)
                if record.xml_sha256 != document.xml_sha256:
                    raise FolioLedgerError(
                        "El mismo emisor, tipo y folio llegó con un XML diferente"
                    )
                if sii_received_at is not None:
                    self._insert_sii_observation(
                        connection, tenant_id, record.id, sii_received_at, now
                    )
                return record
            record_id = str(uuid4())
            try:
                connection.execute(
                    """
                    INSERT INTO received_fiscal_documents (
                        id, tenant_id, receiver_rut, issuer_rut, issuer_name,
                        document_type, folio, issued_on, total, document_id,
                        xml_sha256, signed_xml, source, status, sii_received_at, received_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        record_id,
                        tenant_id,
                        document.receiver_rut,
                        document.issuer_rut,
                        document.issuer_name,
                        int(document.document_type),
                        document.folio,
                        document.issued_on.isoformat(),
                        document.total,
                        document.document_id,
                        document.xml_sha256,
                        document.signed_xml,
                        source,
                        sii_received_at,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise FolioLedgerError("El documento recibido ya fue registrado") from exc
            row = connection.execute(
                "SELECT * FROM received_fiscal_documents WHERE id = ?",
                (record_id,),
            ).fetchone()
            record = _received_document(row)
            for line in document.lines:
                connection.execute(
                    """INSERT INTO received_document_lines
                       (received_document_id,line_number,name,quantity,amount)
                       VALUES (?,?,?,?,?)""",
                    (
                        record.id,
                        line.line_number,
                        line.name,
                        str(line.quantity) if line.quantity is not None else None,
                        line.amount,
                    ),
                )
            if sii_received_at is not None:
                self._insert_sii_observation(
                    connection, tenant_id, record.id, sii_received_at, now
                )
            return record

    def received_document_lines(
        self, received_document_id: str, *, tenant_id: str
    ) -> list[ReceivedLineRecord]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT l.* FROM received_document_lines l
                   JOIN received_fiscal_documents d ON d.id=l.received_document_id
                   WHERE l.received_document_id=? AND d.tenant_id=?
                   ORDER BY l.line_number""",
                (received_document_id, tenant_id),
            ).fetchall()
            return [_received_line(row) for row in rows]

    def latest_sii_reception_observation(
        self, received_document_id: str, *, tenant_id: str
    ) -> ReceivedSiiObservationRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT * FROM received_sii_observations
                   WHERE received_document_id=? AND tenant_id=?
                   ORDER BY observed_at DESC LIMIT 1""",
                (received_document_id, tenant_id),
            ).fetchone()
            return _sii_observation(row) if row is not None else None

    @staticmethod
    def _insert_sii_observation(
        connection, tenant_id: str, record_id: str, sii_received_at: str, now: str
    ) -> None:
        try:
            datetime.fromisoformat(sii_received_at)
        except ValueError as exc:
            raise FolioLedgerError("Fecha de recepción SII inválida") from exc
        connection.execute(
            """INSERT OR IGNORE INTO received_sii_observations
               (id,tenant_id,received_document_id,sii_received_at,observed_at)
               VALUES (?,?,?,?,?)""",
            (str(uuid4()), tenant_id, record_id, sii_received_at, now),
        )

    def received_document_by_id(
        self, record_id: str, *, tenant_id: str
    ) -> ReceivedFiscalDocumentRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM received_fiscal_documents WHERE id = ? AND tenant_id = ?",
                (record_id, tenant_id),
            ).fetchone()
            return _received_document(row) if row is not None else None

    def list_received_documents(
        self,
        *,
        tenant_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReceivedFiscalDocumentRecord]:
        if status is not None and status not in {
            "pending",
            "accepted",
            "claimed_partial",
            "claimed_total",
        }:
            raise FolioLedgerError("Estado de recepción inválido")
        if not 1 <= limit <= 200 or offset < 0:
            raise FolioLedgerError("Paginación inválida")
        query = "SELECT * FROM received_fiscal_documents WHERE tenant_id = ?"
        values: list[object] = [tenant_id]
        if status is not None:
            query += " AND status = ?"
            values.append(status)
        query += " ORDER BY issued_on DESC, received_at DESC LIMIT ? OFFSET ?"
        values.extend((limit, offset))
        with self._connection() as connection:
            return [
                _received_document(row)
                for row in connection.execute(query, values).fetchall()
            ]

    def prepare_received_decision(
        self,
        *,
        tenant_id: str,
        received_document_id: str,
        decision: str,
        reason: str | None,
    ) -> ReceivedDecisionRecord:
        if decision not in {
            "accept_content",
            "ack_receipt",
            "claim_content",
            "claim_partial_delivery",
            "claim_total_delivery",
        }:
            raise FolioLedgerError("Decisión de recepción inválida")
        now = _now()
        with self._transaction() as connection:
            received = connection.execute(
                "SELECT id FROM received_fiscal_documents WHERE id = ? AND tenant_id = ?",
                (received_document_id, tenant_id),
            ).fetchone()
            if received is None:
                raise FolioLedgerError("Documento recibido no encontrado")
            existing_rows = connection.execute(
                "SELECT * FROM received_document_decisions WHERE received_document_id = ?",
                (received_document_id,),
            ).fetchall()
            existing = [_received_decision(row) for row in existing_rows]
            same = next((item for item in existing if item.decision == decision), None)
            if same is not None:
                if same.reason == reason:
                    return same
                raise FolioLedgerError("La misma acción ya existe con otra razón")
            claims = {
                "claim_content",
                "claim_partial_delivery",
                "claim_total_delivery",
            }
            prior = {item.decision for item in existing}
            if (decision in claims and prior & {"accept_content", "ack_receipt"}) or (
                decision in {"accept_content", "ack_receipt"} and prior & claims
            ):
                raise FolioLedgerError("El documento ya tiene una acción incompatible")
            decision_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO received_document_decisions (
                    id, tenant_id, received_document_id, decision, reason, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'prepared', ?, ?)
                """,
                (decision_id, tenant_id, received_document_id, decision, reason, now, now),
            )
            row = connection.execute(
                "SELECT * FROM received_document_decisions WHERE id = ?", (decision_id,)
            ).fetchone()
            return _received_decision(row)

    def received_decision_by_id(
        self, decision_id: str, *, tenant_id: str
    ) -> ReceivedDecisionRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM received_document_decisions WHERE id = ? AND tenant_id = ?",
                (decision_id, tenant_id),
            ).fetchone()
            return _received_decision(row) if row is not None else None

    def begin_received_decision_attempt(
        self, decision_id: str, *, tenant_id: str, request_sha256: str
    ) -> tuple[ReceivedDecisionRecord, ReceivedDecisionAttemptRecord]:
        if len(request_sha256) != 64:
            raise FolioLedgerError("Hash de solicitud inválido")
        now = _now()
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM received_document_decisions WHERE id = ? AND tenant_id = ?",
                (decision_id, tenant_id),
            ).fetchone()
            if row is None:
                raise FolioLedgerError("Decisión no encontrada")
            decision = _received_decision(row)
            if decision.status not in {ReceivedDecisionState.PREPARED}:
                raise FolioLedgerError(
                    "La decisión ya fue enviada o requiere reconciliación"
                )
            attempt_number = connection.execute(
                "SELECT COUNT(*) FROM received_decision_attempts WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()[0] + 1
            attempt_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO received_decision_attempts (
                    id, decision_id, attempt_number, status, request_sha256, started_at
                ) VALUES (?, ?, ?, 'started', ?, ?)
                """,
                (attempt_id, decision_id, attempt_number, request_sha256, now),
            )
            connection.execute(
                "UPDATE received_document_decisions SET status = 'submitting', updated_at = ? WHERE id = ?",
                (now, decision_id),
            )
            updated = connection.execute(
                "SELECT * FROM received_document_decisions WHERE id = ?", (decision_id,)
            ).fetchone()
            attempt = connection.execute(
                "SELECT * FROM received_decision_attempts WHERE id = ?", (attempt_id,)
            ).fetchone()
            return _received_decision(updated), _received_decision_attempt(attempt)

    def complete_received_decision_attempt(
        self,
        attempt_id: str,
        *,
        state: ReceivedDecisionState,
        remote_code: str | None,
        remote_message: str | None,
    ) -> ReceivedDecisionRecord:
        if state not in {
            ReceivedDecisionState.CONFIRMED,
            ReceivedDecisionState.REJECTED,
            ReceivedDecisionState.UNKNOWN,
        }:
            raise FolioLedgerError("Estado final de decisión inválido")
        now = _now()
        attempt_state = {
            ReceivedDecisionState.CONFIRMED: AttemptState.SUCCEEDED,
            ReceivedDecisionState.REJECTED: AttemptState.FAILED,
            ReceivedDecisionState.UNKNOWN: AttemptState.UNKNOWN,
        }[state]
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM received_decision_attempts WHERE id = ?", (attempt_id,)
            ).fetchone()
            if row is None:
                raise FolioLedgerError("Intento de decisión no encontrado")
            attempt = _received_decision_attempt(row)
            if attempt.status is not AttemptState.STARTED:
                raise FolioLedgerError("El intento ya fue finalizado")
            connection.execute(
                """
                UPDATE received_decision_attempts
                SET status = ?, remote_code = ?, remote_message = ?, completed_at = ?
                WHERE id = ?
                """,
                (attempt_state.value, remote_code, remote_message, now, attempt_id),
            )
            connection.execute(
                """
                UPDATE received_document_decisions
                SET status = ?, remote_code = ?, remote_message = ?, updated_at = ?
                WHERE id = ? AND status = 'submitting'
                """,
                (state.value, remote_code, remote_message, now, attempt.decision_id),
            )
            updated = connection.execute(
                "SELECT * FROM received_document_decisions WHERE id = ?",
                (attempt.decision_id,),
            ).fetchone()
            return _received_decision(updated)

    def reconcile_received_decision(
        self,
        decision_id: str,
        *,
        tenant_id: str,
        state: ReceivedDecisionState,
        remote_code: str | None,
        remote_message: str | None,
    ) -> ReceivedDecisionRecord:
        if state not in {
            ReceivedDecisionState.CONFIRMED,
            ReceivedDecisionState.REJECTED,
        }:
            raise FolioLedgerError("La reconciliación debe ser definitiva")
        now = _now()
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM received_document_decisions WHERE id = ? AND tenant_id = ?",
                (decision_id, tenant_id),
            ).fetchone()
            if row is None or _received_decision(row).status is not ReceivedDecisionState.UNKNOWN:
                raise FolioLedgerError("Sólo se reconcilian decisiones desconocidas")
            connection.execute(
                """UPDATE received_document_decisions
                   SET status = ?, remote_code = ?, remote_message = ?, updated_at = ?
                   WHERE id = ?""",
                (state.value, remote_code, remote_message, now, decision_id),
            )
            updated = connection.execute(
                "SELECT * FROM received_document_decisions WHERE id = ?", (decision_id,)
            ).fetchone()
            return _received_decision(updated)

    def classify_received_document(
        self,
        *,
        tenant_id: str,
        received_document_id: str,
        provider_id: str | None,
        destination: str,
        category_code: str | None,
        notes: str | None,
        classified_by: str,
    ) -> ReceivedClassificationRecord:
        if destination not in {
            "expense",
            "inventory",
            "fixed_asset",
            "mixed",
            "unassigned",
        }:
            raise FolioLedgerError("Destino contable inválido")
        _required_token(classified_by, "classified_by")
        for value, label, maximum in (
            (provider_id, "provider_id", 200),
            (category_code, "category_code", 100),
            (notes, "notes", 1000),
        ):
            if value is not None and (not value.strip() or len(value) > maximum):
                raise FolioLedgerError(f"{label} inválido")
        now = _now()
        with self._transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM received_fiscal_documents WHERE id = ? AND tenant_id = ?",
                (received_document_id, tenant_id),
            ).fetchone()
            if exists is None:
                raise FolioLedgerError("Documento recibido no encontrado")
            version = connection.execute(
                "SELECT COUNT(*) FROM received_document_classifications WHERE received_document_id = ?",
                (received_document_id,),
            ).fetchone()[0] + 1
            record_id = str(uuid4())
            connection.execute(
                """INSERT INTO received_document_classifications (
                       id, tenant_id, received_document_id, version, provider_id,
                       destination, category_code, notes, classified_by, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record_id,
                    tenant_id,
                    received_document_id,
                    version,
                    provider_id,
                    destination,
                    category_code,
                    notes,
                    classified_by,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM received_document_classifications WHERE id = ?",
                (record_id,),
            ).fetchone()
            return _received_classification(row)

    def latest_received_classification(
        self, received_document_id: str, *, tenant_id: str
    ) -> ReceivedClassificationRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT * FROM received_document_classifications
                   WHERE received_document_id = ? AND tenant_id = ?
                   ORDER BY version DESC LIMIT 1""",
                (received_document_id, tenant_id),
            ).fetchone()
            return _received_classification(row) if row is not None else None

    def allocate_received_lines(
        self,
        *,
        tenant_id: str,
        classification_id: str,
        allocations: tuple[PurchaseLineAllocation, ...],
    ) -> list[ReceivedLineAllocationRecord]:
        if not allocations or len({item.line_number for item in allocations}) != len(allocations):
            raise FolioLedgerError("Las asignaciones deben contener líneas únicas")
        with self._transaction() as connection:
            classification = connection.execute(
                """SELECT * FROM received_document_classifications
                   WHERE id=? AND tenant_id=?""",
                (classification_id, tenant_id),
            ).fetchone()
            if classification is None:
                raise FolioLedgerError("Clasificación no encontrada")
            valid_lines = {
                row[0]
                for row in connection.execute(
                    "SELECT line_number FROM received_document_lines WHERE received_document_id=?",
                    (classification["received_document_id"],),
                ).fetchall()
            }
            if any(item.line_number not in valid_lines for item in allocations):
                raise FolioLedgerError("La asignación referencia una línea inexistente")
            if classification["destination"] != "mixed" and any(
                item.destination.value != classification["destination"] for item in allocations
            ):
                raise FolioLedgerError("La asignación contradice la clasificación general")
            try:
                for item in allocations:
                    connection.execute(
                        """INSERT INTO received_line_allocations
                           (classification_id,line_number,destination,control_plane_ref)
                           VALUES (?,?,?,?)""",
                        (
                            classification_id,
                            item.line_number,
                            item.destination.value,
                            item.control_plane_ref,
                        ),
                    )
            except sqlite3.IntegrityError as exc:
                raise FolioLedgerError("Las líneas de esta versión ya fueron asignadas") from exc
            rows = connection.execute(
                "SELECT * FROM received_line_allocations WHERE classification_id=? ORDER BY line_number",
                (classification_id,),
            ).fetchall()
            return [_line_allocation(row) for row in rows]

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
                    target == LeaseState.CONSUMED
                    and current.document_id == document_id
                ) or (
                    target == LeaseState.VOIDED
                    and current.void_reason == void_reason
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
            metadata = {"document_id": document_id} if document_id else {"reason": void_reason}
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
            (lease_id, event_type.value, occurred_at, json.dumps(metadata or {}, sort_keys=True)),
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


def _lease(row: sqlite3.Row) -> FolioLease:
    return FolioLease(
        id=row["id"],
        tenant_id=row["tenant_id"],
        taxpayer_rut=row["taxpayer_rut"],
        document_type=row["document_type"],
        folio=row["folio"],
        caf_range_id=row["caf_range_id"],
        idempotency_key=row["idempotency_key"],
        request_sha256=row["request_sha256"],
        status=LeaseState(row["status"]),
        document_id=row["document_id"],
        void_reason=row["void_reason"],
    )


def _document(row: sqlite3.Row) -> FiscalDocumentRecord:
    return FiscalDocumentRecord(
        id=row["id"],
        lease_id=row["lease_id"],
        tenant_id=row["tenant_id"],
        taxpayer_rut=row["taxpayer_rut"],
        document_type=row["document_type"],
        folio=row["folio"],
        document_id=row["document_id"],
        xml_sha256=row["xml_sha256"],
        signed_xml=bytes(row["signed_xml"]),
        created_at=row["created_at"],
        public_id=row["public_id"],
    )


def _envelope(row: sqlite3.Row) -> FiscalEnvelopeRecord:
    return FiscalEnvelopeRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        taxpayer_rut=row["taxpayer_rut"],
        kind=row["kind"],
        document_id=row["document_id"],
        xml_sha256=row["xml_sha256"],
        signed_xml=bytes(row["signed_xml"]),
        status=EnvelopeState(row["status"]),
        track_id=row["track_id"],
        remote_code=row["remote_code"],
        remote_message=row["remote_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _attempt(row: sqlite3.Row) -> SubmissionAttemptRecord:
    return SubmissionAttemptRecord(
        id=row["id"],
        envelope_id=row["envelope_id"],
        attempt_number=row["attempt_number"],
        status=AttemptState(row["status"]),
        request_sha256=row["request_sha256"],
        track_id=row["track_id"],
        response_code=row["response_code"],
        response_message=row["response_message"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


def _delivery(row: sqlite3.Row) -> FiscalDeliveryRecord:
    return FiscalDeliveryRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        document_record_id=row["document_record_id"],
        recipient_email=row["recipient_email"],
        kind=row["kind"],
        exchange_xml_sha256=row["exchange_xml_sha256"],
        exchange_xml=bytes(row["exchange_xml"]),
        pdf_sha256=row["pdf_sha256"],
        pdf=bytes(row["pdf"]),
        status=DeliveryState(row["status"]),
        attempt_count=row["attempt_count"],
        provider_id=row["provider_id"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _received_document(row: sqlite3.Row) -> ReceivedFiscalDocumentRecord:
    return ReceivedFiscalDocumentRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        receiver_rut=row["receiver_rut"],
        issuer_rut=row["issuer_rut"],
        issuer_name=row["issuer_name"],
        document_type=row["document_type"],
        folio=row["folio"],
        issued_on=row["issued_on"],
        total=row["total"],
        document_id=row["document_id"],
        xml_sha256=row["xml_sha256"],
        signed_xml=bytes(row["signed_xml"]),
        source=row["source"],
        status=row["status"],
        sii_received_at=row["sii_received_at"],
        received_at=row["received_at"],
    )


def _received_decision(row: sqlite3.Row) -> ReceivedDecisionRecord:
    return ReceivedDecisionRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        received_document_id=row["received_document_id"],
        decision=row["decision"],
        reason=row["reason"],
        status=ReceivedDecisionState(row["status"]),
        remote_code=row["remote_code"],
        remote_message=row["remote_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _received_decision_attempt(row: sqlite3.Row) -> ReceivedDecisionAttemptRecord:
    return ReceivedDecisionAttemptRecord(
        id=row["id"],
        decision_id=row["decision_id"],
        attempt_number=row["attempt_number"],
        status=AttemptState(row["status"]),
        request_sha256=row["request_sha256"],
        remote_code=row["remote_code"],
        remote_message=row["remote_message"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


def _received_classification(row: sqlite3.Row) -> ReceivedClassificationRecord:
    return ReceivedClassificationRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        received_document_id=row["received_document_id"],
        version=row["version"],
        provider_id=row["provider_id"],
        destination=row["destination"],
        category_code=row["category_code"],
        notes=row["notes"],
        classified_by=row["classified_by"],
        created_at=row["created_at"],
    )


def _sii_observation(row: sqlite3.Row) -> ReceivedSiiObservationRecord:
    return ReceivedSiiObservationRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        received_document_id=row["received_document_id"],
        sii_received_at=row["sii_received_at"],
        observed_at=row["observed_at"],
    )


def _received_line(row: sqlite3.Row) -> ReceivedLineRecord:
    return ReceivedLineRecord(
        received_document_id=row["received_document_id"],
        line_number=row["line_number"],
        name=row["name"],
        quantity=row["quantity"],
        amount=row["amount"],
    )


def _line_allocation(row: sqlite3.Row) -> ReceivedLineAllocationRecord:
    return ReceivedLineAllocationRecord(
        classification_id=row["classification_id"],
        line_number=row["line_number"],
        destination=row["destination"],
        control_plane_ref=row["control_plane_ref"],
    )


def _required_token(value: str, label: str) -> None:
    if not value or not value.strip() or len(value) > 200:
        raise FolioLedgerError(f"{label} debe contener entre 1 y 200 caracteres")


def _xml_total(payload: bytes) -> int:
    try:
        root = etree.fromstring(
            payload,
            etree.XMLParser(resolve_entities=False, no_network=True),
        )
        values = root.xpath("//*[local-name()='MntTotal']/text()")
        if len(values) != 1:
            raise ValueError
        total = int(str(values[0]))
        if total < 0:
            raise ValueError
        return total
    except (etree.XMLSyntaxError, TypeError, ValueError) as exc:
        raise FolioLedgerError("El XML no contiene un MntTotal válido") from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")
