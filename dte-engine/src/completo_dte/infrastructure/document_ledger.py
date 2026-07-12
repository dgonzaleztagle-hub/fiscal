"""Persistencia inmutable de documentos y pertenencia a sobres."""

import hashlib
from uuid import uuid4

from completo_dte.domain import normalize_rut

from .ledger_codec import (
    _document,
    _envelope,
    _lease,
    _now,
    _required_token,
    _xml_total,
)
from .records import (
    FiscalDocumentRecord,
    FiscalEnvelopeRecord,
    FolioLedgerError,
    LeaseState,
)


class DocumentLedgerMixin:
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
            raise FolioLedgerError(
                "Documento corregido y código deben informarse juntos"
            )
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
                    raise FolioLedgerError(
                        "Documento persistido con folio no consumido"
                    )
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
                if lease.document_type not in {56, 61} or correction_code not in {
                    1,
                    2,
                    3,
                }:
                    raise FolioLedgerError(
                        "La relación de corrección no corresponde a la reserva"
                    )
                target_row = connection.execute(
                    "SELECT * FROM fiscal_documents WHERE id = ?",
                    (corrects_record_id,),
                ).fetchone()
                if target_row is None:
                    raise FolioLedgerError("El documento original no existe")
                target = _document(target_row)
                if (
                    target.tenant_id != lease.tenant_id
                    or target.taxpayer_rut != lease.taxpayer_rut
                ):
                    raise FolioLedgerError(
                        "No se puede corregir un documento de otro tenant o emisor"
                    )
                if correction_code == 3 and target.document_type not in {33, 34}:
                    raise FolioLedgerError(
                        "La corrección de montos requiere factura original 33/34"
                    )
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
                        raise FolioLedgerError(
                            "La nota de crédito supera el saldo vigente"
                        )

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
            or any(
                value not in {33, 34, 39, 41, 52, 56, 61} for value in document_types
            )
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
        if not document_record_ids or len(document_record_ids) != len(
            set(document_record_ids)
        ):
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
                    raise FolioLedgerError(
                        "El ID del sobre ya existe con contenido diferente"
                    )
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
                    raise FolioLedgerError(
                        "El sobre contiene documentos de otro tenant o emisor"
                    )
                allowed_types = {
                    "envio_boleta": {39, 41},
                    "envio_dte": {33, 34},
                    "rcof": {39, 41},
                }[kind]
                if record.document_type not in allowed_types:
                    raise FolioLedgerError(
                        "El sobre contiene un tipo documental inválido"
                    )
            claimed = connection.execute(
                f"""
                SELECT document_record_id FROM fiscal_envelope_documents
                WHERE relation_kind = ? AND document_record_id IN ({placeholders})
                """,  # noqa: S608 - sólo placeholders; valores parametrizados.
                (relation_kind, *document_record_ids),
            ).fetchall()
            if claimed:
                raise FolioLedgerError(
                    "Un documento ya pertenece a otro sobre del mismo rol"
                )

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
