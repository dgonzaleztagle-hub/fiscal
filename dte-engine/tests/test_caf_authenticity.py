import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import Encoding

from completo_dte.domain import (
    CafAuthenticityValidator,
    CafError,
    CafLoader,
    CafTrustError,
    SiiCertificateStore,
)
from factories import make_signing_credential, make_synthetic_caf


def make_validator(*, key_id: int = 100):
    sii = make_signing_credential()
    store = SiiCertificateStore()
    certificate_der = sii.certificate.public_bytes(Encoding.DER)
    store.add(
        key_id,
        certificate_der,
        expected_sha256=sii.certificate.fingerprint(hashes.SHA256()).hex(),
    )
    return sii, CafAuthenticityValidator(store)


def test_accepts_caf_signed_by_trusted_sii_certificate() -> None:
    sii, validator = make_validator()
    caf = CafLoader().load(make_synthetic_caf(sii_signing_key=sii.private_key))
    trusted = validator.validate(caf)
    assert trusted.authorization is caf


def test_rejects_tampered_caf_data() -> None:
    sii, validator = make_validator()
    source = make_synthetic_caf(sii_signing_key=sii.private_key)
    tampered = source.replace(b"<H>100</H>", b"<H>101</H>")
    caf = CafLoader().load(tampered)
    with pytest.raises(CafError, match="FRMA"):
        validator.validate(caf)


def test_rejects_unknown_key_id() -> None:
    sii, validator = make_validator(key_id=300)
    caf = CafLoader().load(make_synthetic_caf(key_id=100, sii_signing_key=sii.private_key))
    with pytest.raises(CafTrustError, match="IDK 100"):
        validator.validate(caf)


def test_rejects_certificate_with_wrong_pinned_fingerprint() -> None:
    sii = make_signing_credential()
    store = SiiCertificateStore()
    with pytest.raises(CafTrustError, match="fingerprint"):
        store.add(100, sii.certificate.public_bytes(Encoding.DER), expected_sha256="00" * 32)
