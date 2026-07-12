"""Persistencia de sobres, intentos SII y entregas fiscales."""

import hashlib
from uuid import uuid4

from completo_dte.domain import normalize_rut

from .ledger_codec import _attempt, _delivery, _envelope, _now, _required_token
from .records import (
    AttemptState,
    DeliveryState,
    EnvelopeState,
    FiscalDeliveryRecord,
    FiscalEnvelopeRecord,
    FolioLedgerError,
    SubmissionAttemptRecord,
)


class TransmissionLedgerMixin:
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
                alerts.append(
                    {
                        "code": "caf_exhausted" if remaining == 0 else "caf_low",
                        "severity": "critical" if remaining == 0 else "warning",
                        "message": (
                            f"CAF tipo {row['document_type']} con {remaining} folios disponibles"
                        ),
                        "resource_id": f"{row['taxpayer_rut']}:{row['document_type']}",
                    }
                )
        for row in unknown_rows:
            alerts.append(
                {
                    "code": "envelope_unknown",
                    "severity": "critical",
                    "message": f"{row['kind']} {row['document_id']} requiere conciliación",
                    "resource_id": row["id"],
                }
            )
        if pending_consumption:
            alerts.append(
                {
                    "code": "rcof_pending",
                    "severity": "warning",
                    "message": f"{pending_consumption} boletas aún no están incluidas en RCOF",
                    "resource_id": None,
                }
            )
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
                raise FolioLedgerError(
                    "Sólo las facturas admiten intercambio por esta vía"
                )
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
                    raise FolioLedgerError(
                        "La entrega ya existe con artefactos diferentes"
                    )
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
                    delivery_id,
                    tenant_id,
                    document_record_id,
                    recipient_email,
                    xml_digest,
                    exchange_xml,
                    pdf_digest,
                    pdf,
                    now,
                    now,
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

    def begin_delivery(
        self, delivery_id: str, *, tenant_id: str
    ) -> FiscalDeliveryRecord:
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
                raise FolioLedgerError(
                    "La entrega ambigua debe conciliarse, no reenviarse"
                )
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
        if status not in {
            DeliveryState.SENT,
            DeliveryState.FAILED,
            DeliveryState.UNKNOWN,
        }:
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
                raise FolioLedgerError(
                    "El sobre ya tiene Track ID y no debe reenviarse"
                )
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
