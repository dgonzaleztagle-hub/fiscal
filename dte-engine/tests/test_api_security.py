import pytest
from fastapi import HTTPException

from completo_dte.api.security import build_authenticator


def test_authenticator_resolves_tenant_and_rejects_invalid_credentials() -> None:
    authenticate = build_authenticator({"token-a": "tenant-a", "token-b": "tenant-b"})
    assert authenticate("Bearer token-b").tenant_id == "tenant-b"
    with pytest.raises(HTTPException) as missing:
        authenticate(None)
    assert missing.value.status_code == 401
    with pytest.raises(HTTPException) as invalid:
        authenticate("Bearer invalid")
    assert invalid.value.status_code == 401


@pytest.mark.parametrize("keys", [{}, {"": "tenant"}, {"token": ""}])
def test_authenticator_rejects_incomplete_configuration(keys: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        build_authenticator(keys)
