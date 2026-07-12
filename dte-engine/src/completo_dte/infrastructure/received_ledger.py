"""Persistencia de recepción, decisiones y clasificación de compras."""

import sqlite3
from datetime import datetime
from uuid import uuid4

from completo_dte.domain import PurchaseLineAllocation, ReceivedDocument

from .ledger_codec import (
    _line_allocation,
    _now,
    _received_classification,
    _received_decision,
    _received_decision_attempt,
    _received_document,
    _received_line,
    _required_token,
    _sii_observation,
)
from .records import (
    AttemptState,
    FolioLedgerError,
    ReceivedClassificationRecord,
    ReceivedDecisionAttemptRecord,
    ReceivedDecisionRecord,
    ReceivedDecisionState,
    ReceivedFiscalDocumentRecord,
    ReceivedLineAllocationRecord,
    ReceivedLineRecord,
    ReceivedSiiObservationRecord,
)


class ReceivedLedgerMixin:
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
                raise FolioLedgerError(
                    "El documento recibido ya fue registrado"
                ) from exc
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
                (
                    decision_id,
                    tenant_id,
                    received_document_id,
                    decision,
                    reason,
                    now,
                    now,
                ),
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
            attempt_number = (
                connection.execute(
                    "SELECT COUNT(*) FROM received_decision_attempts WHERE decision_id = ?",
                    (decision_id,),
                ).fetchone()[0]
                + 1
            )
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
            if (
                row is None
                or _received_decision(row).status is not ReceivedDecisionState.UNKNOWN
            ):
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
            version = (
                connection.execute(
                    "SELECT COUNT(*) FROM received_document_classifications WHERE received_document_id = ?",
                    (received_document_id,),
                ).fetchone()[0]
                + 1
            )
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
        if not allocations or len({item.line_number for item in allocations}) != len(
            allocations
        ):
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
                item.destination.value != classification["destination"]
                for item in allocations
            ):
                raise FolioLedgerError(
                    "La asignación contradice la clasificación general"
                )
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
                raise FolioLedgerError(
                    "Las líneas de esta versión ya fueron asignadas"
                ) from exc
            rows = connection.execute(
                "SELECT * FROM received_line_allocations WHERE classification_id=? ORDER BY line_number",
                (classification_id,),
            ).fetchall()
            return [_line_allocation(row) for row in rows]
