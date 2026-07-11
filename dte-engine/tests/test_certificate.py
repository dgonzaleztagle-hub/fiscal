from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from completo_dte.domain import CertificateError, CertificateLoader


NOW = datetime(2026, 7, 8, 12, tzinfo=timezone.utc)


def make_pkcs12(*, not_before: datetime, not_after: datetime) -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CERTIFICADO SINTETICO")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .sign(key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        b"synthetic",
        key,
        certificate,
        None,
        serialization.BestAvailableEncryption(b"test-only"),
    )


def test_loads_valid_synthetic_certificate() -> None:
    payload = make_pkcs12(not_before=NOW - timedelta(days=1), not_after=NOW + timedelta(days=30))
    credential = CertificateLoader().load(payload, "test-only", at=NOW)
    assert credential.subject == "CN=CERTIFICADO SINTETICO"
    assert credential.serial_number


def test_rejects_wrong_password() -> None:
    payload = make_pkcs12(not_before=NOW - timedelta(days=1), not_after=NOW + timedelta(days=30))
    with pytest.raises(CertificateError, match="contraseña"):
        CertificateLoader().load(payload, "wrong", at=NOW)


def test_rejects_expired_certificate() -> None:
    payload = make_pkcs12(not_before=NOW - timedelta(days=30), not_after=NOW - timedelta(days=1))
    with pytest.raises(CertificateError, match="vencido"):
        CertificateLoader().load(payload, "test-only", at=NOW)

