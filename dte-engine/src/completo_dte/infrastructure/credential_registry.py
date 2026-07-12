"""Registro de referencias opacas; jamás almacena PFX o contraseñas."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from completo_dte.domain import normalize_rut

from .folio_ledger import FolioLedgerError


@dataclass(frozen=True)
class CredentialReferenceRecord:
    id: str
    tenant_id: str
    taxpayer_rut: str
    vault_ref: str
    certificate_sha256: str
    active_from: str
    retired_at: str | None
    created_at: str


class CredentialReferenceRegistry:
    def __init__(self, database: str | Path) -> None:
        self._database = str(database)

    def rotate(
        self,
        *,
        tenant_id: str,
        taxpayer_rut: str,
        vault_ref: str,
        certificate_sha256: str,
        active_from: datetime,
    ) -> CredentialReferenceRecord:
        if not vault_ref.startswith("vault://") or len(vault_ref) > 500:
            raise FolioLedgerError("Referencia de vault inválida")
        if len(certificate_sha256) != 64 or any(
            char not in "0123456789abcdefABCDEF" for char in certificate_sha256
        ):
            raise FolioLedgerError("Fingerprint de certificado inválido")
        if active_from.tzinfo is None:
            raise FolioLedgerError("La activación debe incluir zona horaria")
        taxpayer_rut = normalize_rut(taxpayer_rut)
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                """SELECT * FROM issuer_credential_references
                   WHERE tenant_id=? AND taxpayer_rut=? AND retired_at IS NULL""",
                (tenant_id, taxpayer_rut),
            ).fetchone()
            if (
                current is not None
                and current["certificate_sha256"].lower() == certificate_sha256.lower()
            ):
                connection.execute("COMMIT")
                return _record(current)
            connection.execute(
                """UPDATE issuer_credential_references SET retired_at=?
                   WHERE tenant_id=? AND taxpayer_rut=? AND retired_at IS NULL""",
                (active_from.isoformat(), tenant_id, taxpayer_rut),
            )
            record_id = str(uuid4())
            connection.execute(
                """INSERT INTO issuer_credential_references
                   (id,tenant_id,taxpayer_rut,vault_ref,certificate_sha256,active_from,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    record_id,
                    tenant_id,
                    taxpayer_rut,
                    vault_ref,
                    certificate_sha256.lower(),
                    active_from.isoformat(),
                    now,
                ),
            )
            connection.execute("COMMIT")
            row = connection.execute(
                "SELECT * FROM issuer_credential_references WHERE id=?", (record_id,)
            ).fetchone()
            return _record(row)
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def active(
        self, *, tenant_id: str, taxpayer_rut: str
    ) -> CredentialReferenceRecord | None:
        connection = self._connect()
        try:
            row = connection.execute(
                """SELECT * FROM issuer_credential_references
                   WHERE tenant_id=? AND taxpayer_rut=? AND retired_at IS NULL""",
                (tenant_id, normalize_rut(taxpayer_rut)),
            ).fetchone()
            return _record(row) if row is not None else None
        finally:
            connection.close()

    def _connect(self):
        connection = sqlite3.connect(self._database, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection


def _record(row) -> CredentialReferenceRecord:
    return CredentialReferenceRecord(**dict(row))
