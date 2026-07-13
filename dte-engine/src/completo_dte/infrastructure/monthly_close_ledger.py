"""Persistencia append-only para versiones y revisiones del cierre mensual."""

from dataclasses import dataclass
import json
from typing import Any
from uuid import uuid4

from .ledger_codec import _now, _required_token
from .records import FolioLedgerError


@dataclass(frozen=True)
class MonthlyCloseRecord:
    id: str
    tenant_id: str
    period: str
    version: int
    formula_version: str
    source_sha256: str
    calculation_sha256: str
    payload: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class MonthlyCloseReviewRecord:
    id: str
    snapshot_id: str
    tenant_id: str
    actor_ref: str
    action: str
    reason: str | None
    occurred_at: str


class MonthlyCloseLedgerMixin:
    def persist_monthly_close(
        self,
        *,
        tenant_id: str,
        period: str,
        formula_version: str,
        source_sha256: str,
        calculation_sha256: str,
        payload: dict[str, Any],
    ) -> MonthlyCloseRecord:
        _required_token(tenant_id, "tenant_id")
        _required_token(formula_version, "formula_version")
        if len(period) != 7 or period[4] != "-":
            raise FolioLedgerError("El período debe usar formato YYYY-MM")
        if len(source_sha256) != 64 or len(calculation_sha256) != 64:
            raise FolioLedgerError("Los hashes del cierre deben ser SHA-256")
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._transaction() as connection:
            existing = connection.execute(
                """
                SELECT * FROM monthly_close_snapshots
                WHERE tenant_id = ? AND period = ? AND calculation_sha256 = ?
                """,
                (tenant_id, period, calculation_sha256),
            ).fetchone()
            if existing is not None:
                return _close_record(existing)
            version = connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                FROM monthly_close_snapshots WHERE tenant_id = ? AND period = ?
                """,
                (tenant_id, period),
            ).fetchone()["next_version"]
            record_id = str(uuid4())
            created_at = _now()
            connection.execute(
                """
                INSERT INTO monthly_close_snapshots (
                    id, tenant_id, period, version, formula_version, source_sha256,
                    calculation_sha256, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    tenant_id,
                    period,
                    version,
                    formula_version,
                    source_sha256,
                    calculation_sha256,
                    encoded,
                    created_at,
                ),
            )
            row = connection.execute(
                "SELECT * FROM monthly_close_snapshots WHERE id = ?", (record_id,)
            ).fetchone()
        return _close_record(row)

    def list_monthly_closes(
        self, *, tenant_id: str, period: str
    ) -> tuple[MonthlyCloseRecord, ...]:
        _required_token(tenant_id, "tenant_id")
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM monthly_close_snapshots
                WHERE tenant_id = ? AND period = ? ORDER BY version DESC
                """,
                (tenant_id, period),
            ).fetchall()
        return tuple(_close_record(row) for row in rows)

    def review_monthly_close(
        self,
        *,
        tenant_id: str,
        snapshot_id: str,
        actor_ref: str,
        action: str,
        reason: str | None = None,
    ) -> MonthlyCloseReviewRecord:
        for value, name in ((tenant_id, "tenant_id"), (snapshot_id, "snapshot_id"), (actor_ref, "actor_ref")):
            _required_token(value, name)
        transitions = {
            None: "opened",
            "opened": "marked_ready",
            "marked_ready": "reviewed",
            "reviewed": "frozen",
        }
        with self._transaction() as connection:
            snapshot = connection.execute(
                "SELECT id FROM monthly_close_snapshots WHERE id = ? AND tenant_id = ?",
                (snapshot_id, tenant_id),
            ).fetchone()
            if snapshot is None:
                raise FolioLedgerError("El cierre no existe para el tenant")
            previous = connection.execute(
                """
                SELECT action FROM monthly_close_reviews
                WHERE snapshot_id = ? AND tenant_id = ?
                ORDER BY occurred_at DESC, rowid DESC LIMIT 1
                """,
                (snapshot_id, tenant_id),
            ).fetchone()
            previous_action = previous["action"] if previous else None
            if transitions.get(previous_action) != action:
                raise FolioLedgerError("La transición de revisión del cierre no es válida")
            record_id = str(uuid4())
            occurred_at = _now()
            connection.execute(
                """
                INSERT INTO monthly_close_reviews (
                    id, snapshot_id, tenant_id, actor_ref, action, reason, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, snapshot_id, tenant_id, actor_ref, action, reason, occurred_at),
            )
        return MonthlyCloseReviewRecord(
            record_id, snapshot_id, tenant_id, actor_ref, action, reason, occurred_at
        )


def _close_record(row) -> MonthlyCloseRecord:
    return MonthlyCloseRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        period=row["period"],
        version=row["version"],
        formula_version=row["formula_version"],
        source_sha256=row["source_sha256"],
        calculation_sha256=row["calculation_sha256"],
        payload=json.loads(row["payload_json"]),
        created_at=row["created_at"],
    )
