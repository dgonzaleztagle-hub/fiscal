from datetime import datetime, timedelta, timezone

from completo_dte.infrastructure import CredentialReferenceRegistry, FolioLedger


def test_rotation_retires_previous_reference_and_isolates_tenants(tmp_path) -> None:
    database = tmp_path / "credentials.sqlite3"
    FolioLedger(database).migrate()
    registry = CredentialReferenceRegistry(database)
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    first = registry.rotate(
        tenant_id="tenant-a", taxpayer_rut="12345678-5",
        vault_ref="vault://fiscal/tenant-a/cert-v1",
        certificate_sha256="a" * 64, active_from=now,
    )
    second = registry.rotate(
        tenant_id="tenant-a", taxpayer_rut="12345678-5",
        vault_ref="vault://fiscal/tenant-a/cert-v2",
        certificate_sha256="b" * 64, active_from=now + timedelta(days=20),
    )
    assert first.id != second.id
    assert registry.active(tenant_id="tenant-a", taxpayer_rut="12345678-5") == second
    assert registry.active(tenant_id="tenant-b", taxpayer_rut="12345678-5") is None
    connection = registry._connect()
    try:
        old = connection.execute(
            "SELECT retired_at FROM issuer_credential_references WHERE id=?", (first.id,)
        ).fetchone()
        assert old["retired_at"] == (now + timedelta(days=20)).isoformat()
        columns = {row[1] for row in connection.execute("PRAGMA table_info(issuer_credential_references)")}
        assert "pfx" not in columns
        assert "password" not in columns
    finally:
        connection.close()


def test_same_certificate_rotation_is_idempotent(tmp_path) -> None:
    database = tmp_path / "credentials.sqlite3"
    FolioLedger(database).migrate()
    registry = CredentialReferenceRegistry(database)
    kwargs = dict(
        tenant_id="tenant-a", taxpayer_rut="12345678-5",
        vault_ref="vault://fiscal/tenant-a/cert-v1",
        certificate_sha256="a" * 64,
        active_from=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    assert registry.rotate(**kwargs) == registry.rotate(**kwargs)
