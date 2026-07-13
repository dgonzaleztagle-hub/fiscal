"""Persistencia tenant-first de cotizaciones y órdenes."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
import secrets
from datetime import datetime,timezone
from uuid import uuid4

from completo_dte.domain.commercial import (
    CommercialDocument, CommercialDocumentKind, CommercialDocumentStatus,
    CommercialLine,
)
from .ledger_codec import _now, _required_token
from .records import FolioLedgerError


@dataclass(frozen=True)
class CommercialRecord:
    id: str
    tenant_id: str
    kind: str
    number: int
    branch_id: str
    counterparty_ref: str
    counterparty_name: str
    issued_on: str
    valid_until: str | None
    currency: str
    status: str
    notes: str
    total: int
    converted_document_id: str | None
    created_at: str
    updated_at: str
    lines: tuple[CommercialLine, ...]


class CommercialLedgerMixin:
    def get_commercial_document(self, *, tenant_id:str, record_id:str) -> CommercialRecord:
        with self._connection() as connection:
            row=connection.execute("SELECT * FROM commercial_documents WHERE id=? AND tenant_id=?",(record_id,tenant_id)).fetchone()
            if not row:raise FolioLedgerError("Documento comercial no encontrado")
            return self._commercial_record(connection,row)
    def create_commercial_public_link(self, *, tenant_id:str, record_id:str, expires_at:str):
        token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest()
        with self._transaction() as connection:
            row=connection.execute("SELECT * FROM commercial_documents WHERE id=? AND tenant_id=? AND kind='quote'",(record_id,tenant_id)).fetchone()
            if not row:raise FolioLedgerError("Cotización no encontrada")
            if row["status"] not in {"draft","sent"}:raise FolioLedgerError("La cotización ya no admite un enlace de decisión")
            connection.execute("UPDATE commercial_documents SET status='sent',updated_at=? WHERE id=?",(_now(),record_id))
            connection.execute("INSERT INTO commercial_public_links VALUES (?,?,?,?,?,?,?,?,?)",(str(uuid4()),tenant_id,record_id,digest,"quote_decision",expires_at,None,None,_now()))
        return token

    def inspect_commercial_public_link(self, *, token:str):
        digest=hashlib.sha256(token.encode()).hexdigest()
        with self._connection() as connection:
            link=connection.execute("SELECT * FROM commercial_public_links WHERE token_sha256=?",(digest,)).fetchone()
            if not link or link["used_at"]:raise FolioLedgerError("Enlace inválido o utilizado")
            if datetime.fromisoformat(link["expires_at"]).astimezone(timezone.utc)<=datetime.now(timezone.utc):raise FolioLedgerError("Enlace vencido")
            row=connection.execute("SELECT * FROM commercial_documents WHERE id=?",(link["commercial_document_id"],)).fetchone()
            return self._commercial_record(connection,row)

    def decide_commercial_public_link(self, *, token:str, decision:str):
        if decision not in {"accepted","rejected"}:raise FolioLedgerError("Decisión pública inválida")
        digest=hashlib.sha256(token.encode()).hexdigest()
        with self._transaction() as connection:
            link=connection.execute("SELECT * FROM commercial_public_links WHERE token_sha256=?",(digest,)).fetchone()
            if not link or link["used_at"]:raise FolioLedgerError("Enlace inválido o utilizado")
            if datetime.fromisoformat(link["expires_at"]).astimezone(timezone.utc)<=datetime.now(timezone.utc):raise FolioLedgerError("Enlace vencido")
            row=connection.execute("SELECT * FROM commercial_documents WHERE id=?",(link["commercial_document_id"],)).fetchone()
            if row["status"]!="sent":raise FolioLedgerError("La cotización ya fue resuelta")
            now=_now();connection.execute("UPDATE commercial_public_links SET used_at=?,decision=? WHERE id=?",(now,decision,link["id"]));connection.execute("UPDATE commercial_documents SET status=?,updated_at=? WHERE id=?",(decision,now,row["id"]));self._append_commercial_event(connection,row["tenant_id"],row["id"],f"public_{decision}","public-link",{})
            return self._commercial_record(connection,connection.execute("SELECT * FROM commercial_documents WHERE id=?",(row["id"],)).fetchone())
    def create_commercial_document(self, *, tenant_id: str, idempotency_key: str,
                                   document: CommercialDocument,
                                   actor_ref: str) -> CommercialRecord:
        _required_token(tenant_id, "tenant_id")
        _required_token(idempotency_key, "idempotency_key")
        _required_token(actor_ref, "actor_ref")
        payload = _document_payload(document)
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        now = _now()
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM commercial_documents WHERE tenant_id=? AND idempotency_key=?",
                (tenant_id, idempotency_key),
            ).fetchone()
            if existing:
                if existing["request_sha256"] != digest:
                    raise FolioLedgerError("La idempotency key comercial fue reutilizada con otros datos")
                return self._commercial_record(connection, existing)
            number = connection.execute(
                "SELECT COALESCE(MAX(number),0)+1 value FROM commercial_documents WHERE tenant_id=? AND kind=?",
                (tenant_id, document.kind.value),
            ).fetchone()["value"]
            record_id = str(uuid4())
            connection.execute(
                """INSERT INTO commercial_documents
                (id,tenant_id,kind,number,branch_id,counterparty_ref,counterparty_name,
                 issued_on,valid_until,currency,status,notes,total,idempotency_key,
                 request_sha256,converted_document_id,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (record_id, tenant_id, document.kind.value, number, document.branch_id,
                 document.counterparty_ref, document.counterparty_name,
                 document.issued_on.isoformat(), document.valid_until.isoformat() if document.valid_until else None,
                 document.currency, CommercialDocumentStatus.DRAFT.value, document.notes,
                 document.total, idempotency_key, digest, None, now, now),
            )
            for index, line in enumerate(document.lines, 1):
                connection.execute(
                    "INSERT INTO commercial_document_lines VALUES (?,?,?,?,?,?,?,?,?)",
                    (str(uuid4()), record_id, index, line.product_ref, line.description,
                     str(line.quantity), str(line.unit_price), str(line.discount_percent), line.subtotal),
                )
            self._append_commercial_event(connection, tenant_id, record_id, "created", actor_ref, {})
            row = connection.execute("SELECT * FROM commercial_documents WHERE id=?", (record_id,)).fetchone()
            return self._commercial_record(connection, row)

    def list_commercial_documents(self, *, tenant_id: str, kind: str | None = None,
                                  status: str | None = None) -> tuple[CommercialRecord, ...]:
        clauses, params = ["tenant_id=?"], [tenant_id]
        if kind:
            CommercialDocumentKind(kind)
            clauses.append("kind=?"); params.append(kind)
        if status:
            CommercialDocumentStatus(status)
            clauses.append("status=?"); params.append(status)
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM commercial_documents WHERE {' AND '.join(clauses)} ORDER BY issued_on DESC, number DESC",
                params,
            ).fetchall()
            return tuple(self._commercial_record(connection, row) for row in rows)

    def transition_commercial_document(self, *, tenant_id: str, record_id: str,
                                       target_status: str, actor_ref: str,
                                       converted_document_id: str | None = None) -> CommercialRecord:
        target = CommercialDocumentStatus(target_status)
        allowed = {
            "draft": {"sent", "accepted", "cancelled"},
            "sent": {"accepted", "rejected", "cancelled"},
            "accepted": {"converted", "cancelled"},
            "rejected": set(), "cancelled": set(), "converted": set(),
        }
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM commercial_documents WHERE id=? AND tenant_id=?", (record_id, tenant_id)
            ).fetchone()
            if not row:
                raise FolioLedgerError("Documento comercial no encontrado")
            if target.value not in allowed[row["status"]]:
                raise FolioLedgerError(f"Transición comercial inválida: {row['status']} → {target.value}")
            if target is CommercialDocumentStatus.CONVERTED and not converted_document_id:
                raise FolioLedgerError("La conversión requiere el documento resultante")
            now = _now()
            connection.execute(
                "UPDATE commercial_documents SET status=?,converted_document_id=?,updated_at=? WHERE id=?",
                (target.value, converted_document_id, now, record_id),
            )
            self._append_commercial_event(connection, tenant_id, record_id, target.value, actor_ref,
                                          {"converted_document_id": converted_document_id} if converted_document_id else {})
            row = connection.execute("SELECT * FROM commercial_documents WHERE id=?", (record_id,)).fetchone()
            return self._commercial_record(connection, row)

    def _append_commercial_event(self, connection, tenant_id, record_id, event_type, actor_ref, metadata):
        connection.execute("INSERT INTO commercial_events VALUES (?,?,?,?,?,?,?)",
                           (str(uuid4()), tenant_id, record_id, event_type, actor_ref,
                            json.dumps(metadata, sort_keys=True), _now()))

    def _commercial_record(self, connection, row) -> CommercialRecord:
        lines = connection.execute(
            "SELECT * FROM commercial_document_lines WHERE commercial_document_id=? ORDER BY line_number", (row["id"],)
        ).fetchall()
        return CommercialRecord(
            **{key: row[key] for key in ("id","tenant_id","kind","number","branch_id","counterparty_ref",
                "counterparty_name","issued_on","valid_until","currency","status","notes","total",
                "converted_document_id","created_at","updated_at")},
            lines=tuple(CommercialLine(line["description"], Decimal(line["quantity"]),
                Decimal(line["unit_price"]), Decimal(line["discount_percent"]), line["product_ref"]) for line in lines),
        )


def _document_payload(document: CommercialDocument) -> dict:
    return {"kind": document.kind.value, "branch_id": document.branch_id,
            "counterparty_ref": document.counterparty_ref, "counterparty_name": document.counterparty_name,
            "issued_on": document.issued_on.isoformat(),
            "valid_until": document.valid_until.isoformat() if document.valid_until else None,
            "currency": document.currency, "notes": document.notes,
            "lines": [{"description": line.description, "quantity": str(line.quantity),
                       "unit_price": str(line.unit_price), "discount_percent": str(line.discount_percent),
                       "product_ref": line.product_ref} for line in document.lines]}
