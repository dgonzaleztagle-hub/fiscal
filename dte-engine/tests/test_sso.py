from datetime import datetime, timedelta, timezone

import pytest

from completo_dte.application import OneTimeSsoService, SsoError
from completo_dte.infrastructure import FolioLedger


def service(tmp_path):
    database = tmp_path / "sso.sqlite3"
    FolioLedger(database).migrate()
    return OneTimeSsoService(database=database, signing_key=b"s" * 32)


def test_sso_is_bound_to_user_tenant_destination_and_single_use(tmp_path) -> None:
    sso = service(tmp_path)
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    code = sso.issue(
        user_id="user-1",
        tenant_id="tenant-a",
        destination="fiscal",
        now=now,
    )
    identity = sso.consume(code, expected_destination="fiscal", now=now)
    assert identity == {
        "user_id": "user-1",
        "tenant_id": "tenant-a",
        "destination": "fiscal",
    }
    with pytest.raises(SsoError, match="ya utilizado"):
        sso.consume(code, expected_destination="fiscal", now=now)


def test_sso_rejects_wrong_destination_expiry_and_tampering(tmp_path) -> None:
    sso = service(tmp_path)
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    code = sso.issue(
        user_id="user-1", tenant_id="tenant-a", destination="fiscal", now=now
    )
    with pytest.raises(SsoError, match="otro destino"):
        sso.consume(code, expected_destination="gastro", now=now)
    with pytest.raises(SsoError, match="vencido"):
        sso.consume(code, expected_destination="fiscal", now=now + timedelta(seconds=61))
    tampered = ("A" if code[0] != "A" else "B") + code[1:]
    with pytest.raises(SsoError, match="Firma SSO"):
        sso.consume(tampered, expected_destination="fiscal", now=now)


def test_sso_ttl_cannot_exceed_sixty_seconds(tmp_path) -> None:
    with pytest.raises(SsoError, match="60 segundos"):
        service(tmp_path).issue(
            user_id="user-1",
            tenant_id="tenant-a",
            destination="fiscal",
            ttl_seconds=61,
        )
