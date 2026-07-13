"""Autenticación tenant-first de la frontera HTTP."""

import hashlib
import hmac
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Header, HTTPException, status


@dataclass(frozen=True)
class ApiPrincipal:
    tenant_id: str
    actor_ref: str = "api-key"
    roles: frozenset[str] = frozenset({"system"})
    entitlements: frozenset[str] = frozenset({"fiscal"})


def build_authenticator(api_keys: dict[str, str | ApiPrincipal]) -> Callable[..., ApiPrincipal]:
    """Compila tokens a hashes y devuelve una dependencia FastAPI constante en tiempo."""
    if not api_keys:
        raise ValueError("Se requiere al menos una API key")
    hashed_keys = tuple(
        (_token_digest(token), value if isinstance(value,ApiPrincipal) else ApiPrincipal(value))
        for token, value in api_keys.items()
        if token and value
    )
    if len(hashed_keys) != len(api_keys):
        raise ValueError("API keys y tenant IDs no pueden estar vacíos")

    def authenticate(authorization: str | None = Header(default=None)) -> ApiPrincipal:
        if authorization is None or not authorization.startswith("Bearer "):
            raise _unauthorized("Bearer token requerido")
        supplied = _token_digest(authorization.removeprefix("Bearer ").strip())
        matched: ApiPrincipal | None = None
        for expected, principal in hashed_keys:
            if hmac.compare_digest(supplied, expected):
                matched = principal
        if matched is None:
            raise _unauthorized("Credencial inválida")
        return matched

    return authenticate


def _token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
