"""Ledger append-only de vouchers y conciliaciones electrónicas."""

from dataclasses import dataclass
import hashlib
import json
from typing import Any
from uuid import uuid4

from .ledger_codec import _now, _required_token
from .records import FolioLedgerError


@dataclass(frozen=True)
class ElectronicPaymentRecord:
    id: str
    tenant_id: str
    provider: str
    terminal_id: str
    authorization_code: str
    provider_reference: str
    sale_ref: str
    amount: int
    occurred_at: str
    settlement_ref: str | None
    source: str
    imported_at: str


@dataclass(frozen=True)
class PaymentReconciliationRecord:
    id: str
    tenant_id: str
    period: str
    version: int
    payload_sha256: str
    payload: dict[str, Any]
    created_at: str


class PaymentLedgerMixin:
    def persist_people_summary(
        self, *, tenant_id: str, period: str, payload_sha256: str,
        payload: dict[str, Any]
    ) -> PaymentReconciliationRecord:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM people_monthly_summaries WHERE tenant_id=? AND period=? AND payload_sha256=?",
                (tenant_id, period, payload_sha256),
            ).fetchone()
            if existing is not None:
                return _people_record(existing)
            version = connection.execute(
                "SELECT COALESCE(MAX(version),0)+1 value FROM people_monthly_summaries WHERE tenant_id=? AND period=?",
                (tenant_id, period),
            ).fetchone()["value"]
            record_id, imported_at = str(uuid4()), _now()
            connection.execute(
                "INSERT INTO people_monthly_summaries VALUES (?,?,?,?,?,?,?)",
                (record_id, tenant_id, period, version, payload_sha256, encoded, imported_at),
            )
            row = connection.execute("SELECT * FROM people_monthly_summaries WHERE id=?", (record_id,)).fetchone()
        return _people_record(row)

    def latest_people_summary(self, *, tenant_id: str, period: str):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM people_monthly_summaries WHERE tenant_id=? AND period=? ORDER BY version DESC LIMIT 1",
                (tenant_id, period),
            ).fetchone()
        return _people_record(row) if row else None

    def import_electronic_payment(
        self,
        *,
        tenant_id: str,
        provider: str,
        terminal_id: str,
        authorization_code: str,
        provider_reference: str,
        sale_ref: str,
        amount: int,
        occurred_at: str,
        settlement_ref: str | None,
        source: str,
    ) -> ElectronicPaymentRecord:
        for value, name in (
            (tenant_id, "tenant_id"),
            (provider, "provider"),
            (terminal_id, "terminal_id"),
            (authorization_code, "authorization_code"),
            (provider_reference, "provider_reference"),
            (sale_ref, "sale_ref"),
            (occurred_at, "occurred_at"),
        ):
            _required_token(value, name)
        if amount <= 0:
            raise FolioLedgerError("El monto del voucher debe ser positivo")
        if source not in {"pos_integration", "provider_import", "manual"}:
            raise FolioLedgerError("Fuente de voucher inválida")
        with self._transaction() as connection:
            existing = connection.execute(
                """
                SELECT * FROM electronic_payments
                WHERE tenant_id=? AND provider=? AND terminal_id=?
                  AND authorization_code=? AND provider_reference=?
                """,
                (tenant_id, provider, terminal_id, authorization_code, provider_reference),
            ).fetchone()
            if existing is not None:
                if existing["amount"] != amount or existing["sale_ref"] != sale_ref:
                    raise FolioLedgerError("El voucher ya existe con contenido diferente")
                return _payment(existing)
            record_id = str(uuid4())
            imported_at = _now()
            connection.execute(
                """
                INSERT INTO electronic_payments (
                    id,tenant_id,provider,terminal_id,authorization_code,
                    provider_reference,sale_ref,amount,occurred_at,settlement_ref,
                    source,imported_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (record_id,tenant_id,provider,terminal_id,authorization_code,
                 provider_reference,sale_ref,amount,occurred_at,settlement_ref,
                 source,imported_at),
            )
            row = connection.execute(
                "SELECT * FROM electronic_payments WHERE id=?", (record_id,)
            ).fetchone()
        return _payment(row)

    def list_electronic_payments(
        self, *, tenant_id: str, period: str
    ) -> tuple[ElectronicPaymentRecord, ...]:
        _required_token(tenant_id, "tenant_id")
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM electronic_payments
                WHERE tenant_id=? AND substr(occurred_at,1,7)=?
                ORDER BY occurred_at, id
                """,
                (tenant_id, period),
            ).fetchall()
        return tuple(_payment(row) for row in rows)

    def persist_payment_reconciliation(
        self, *, tenant_id: str, period: str, payload: dict[str, Any]
    ) -> PaymentReconciliationRecord:
        _required_token(tenant_id, "tenant_id")
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self._transaction() as connection:
            existing = connection.execute(
                """SELECT * FROM payment_reconciliation_snapshots
                   WHERE tenant_id=? AND period=? AND payload_sha256=?""",
                (tenant_id, period, digest),
            ).fetchone()
            if existing is not None:
                return _reconciliation(existing)
            version = connection.execute(
                """SELECT COALESCE(MAX(version),0)+1 AS value
                   FROM payment_reconciliation_snapshots
                   WHERE tenant_id=? AND period=?""",
                (tenant_id, period),
            ).fetchone()["value"]
            record_id = str(uuid4())
            created_at = _now()
            connection.execute(
                """INSERT INTO payment_reconciliation_snapshots
                   (id,tenant_id,period,version,payload_sha256,payload_json,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (record_id, tenant_id, period, version, digest, encoded, created_at),
            )
            row = connection.execute(
                "SELECT * FROM payment_reconciliation_snapshots WHERE id=?", (record_id,)
            ).fetchone()
        return _reconciliation(row)

    def latest_payment_reconciliation(
        self, *, tenant_id: str, period: str
    ) -> PaymentReconciliationRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT * FROM payment_reconciliation_snapshots
                   WHERE tenant_id=? AND period=? ORDER BY version DESC LIMIT 1""",
                (tenant_id, period),
            ).fetchone()
        return _reconciliation(row) if row is not None else None


def _payment(row) -> ElectronicPaymentRecord:
    return ElectronicPaymentRecord(**dict(row))


def _reconciliation(row) -> PaymentReconciliationRecord:
    return PaymentReconciliationRecord(
        row["id"], row["tenant_id"], row["period"], row["version"],
        row["payload_sha256"], json.loads(row["payload_json"]), row["created_at"]
    )


def _people_record(row) -> PaymentReconciliationRecord:
    return PaymentReconciliationRecord(
        row["id"], row["tenant_id"], row["period"], row["version"],
        row["payload_sha256"], json.loads(row["payload_json"]), row["imported_at"]
    )
