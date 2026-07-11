"""Código SSO firmado, efímero y de un solo uso entre productos Completo."""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3


class SsoError(ValueError):
    pass


class OneTimeSsoService:
    def __init__(self, *, database: str | Path, signing_key: bytes) -> None:
        if len(signing_key) < 32:
            raise SsoError("La clave SSO debe tener al menos 32 bytes")
        self._database = str(database)
        self._key = signing_key

    def issue(
        self,
        *,
        user_id: str,
        tenant_id: str,
        destination: str,
        now: datetime | None = None,
        ttl_seconds: int = 60,
    ) -> str:
        if not 1 <= ttl_seconds <= 60:
            raise SsoError("El código SSO no puede vivir más de 60 segundos")
        for value, label in (
            (user_id, "user_id"),
            (tenant_id, "tenant_id"),
            (destination, "destination"),
        ):
            if not value or len(value) > 200 or any(char.isspace() for char in value):
                raise SsoError(f"{label} inválido")
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise SsoError("La hora SSO debe incluir zona horaria")
        payload = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "destination": destination,
            "nonce": secrets.token_urlsafe(24),
            "exp": int((instant + timedelta(seconds=ttl_seconds)).timestamp()),
        }
        encoded = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        signature = _b64(hmac.new(self._key, encoded.encode(), hashlib.sha256).digest())
        return f"{encoded}.{signature}"

    def consume(
        self,
        code: str,
        *,
        expected_destination: str,
        now: datetime | None = None,
    ) -> dict[str, str]:
        try:
            encoded, signature = code.split(".", 1)
            expected = _b64(hmac.new(self._key, encoded.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(signature, expected):
                raise SsoError("Firma SSO inválida")
            payload = json.loads(_unb64(encoded))
        except SsoError:
            raise
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SsoError("Código SSO malformado") from exc
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None or int(instant.timestamp()) > int(payload.get("exp", 0)):
            raise SsoError("Código SSO vencido")
        if payload.get("destination") != expected_destination:
            raise SsoError("El código SSO pertenece a otro destino")
        required = ("nonce", "tenant_id", "user_id", "destination")
        if any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
            raise SsoError("Payload SSO incompleto")
        connection = sqlite3.connect(self._database, timeout=30, isolation_level=None)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO consumed_sso_nonces
                   (nonce,tenant_id,user_id,destination,consumed_at)
                   VALUES (?,?,?,?,?)""",
                (
                    payload["nonce"], payload["tenant_id"], payload["user_id"],
                    payload["destination"], instant.isoformat(timespec="microseconds"),
                ),
            )
            connection.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise SsoError("Código SSO ya utilizado") from exc
        finally:
            connection.close()
        return {
            "user_id": payload["user_id"],
            "tenant_id": payload["tenant_id"],
            "destination": payload["destination"],
        }


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
