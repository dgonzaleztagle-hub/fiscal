import base64
from datetime import datetime, timedelta, timezone
import re

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from completo_dte.domain import (
    CafAuthenticityValidator,
    CafLoader,
    SiiCertificateStore,
    SigningCredential,
    TrustedCafAuthorization,
)


def make_synthetic_caf(
    *,
    issuer_rut: str = "12345678-5",
    document_type: int = 39,
    folio_from: int = 1,
    folio_to: int = 100,
    key_id: int = 100,
    sii_signing_key: rsa.RSAPrivateKey | None = None,
) -> bytes:
    # Los CAF históricos usan claves heredadas más pequeñas que el certificado
    # del emisor. Mantener esa proporción también permite probar el PDF417 real.
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    numbers = key.public_key().public_numbers()
    modulus = base64.b64encode(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")).decode()
    exponent = base64.b64encode(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")).decode()
    der = key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    private = base64.b64encode(der).decode()
    caf_without_signature = (
        f'<CAF version="1.0"><DA>'
        f"<RE>{issuer_rut}</RE><RS>RESTAURANTE SINTETICO SPA</RS><TD>{document_type}</TD>"
        f"<RNG><D>{folio_from}</D><H>{folio_to}</H></RNG><FA>2026-07-08</FA>"
        f"<RSAPK><M>{modulus}</M><E>{exponent}</E></RSAPK><IDK>{key_id}</IDK>"
        "</DA>"
    )
    signature = b"synthetic-signature"
    if sii_signing_key is not None:
        da = etree.fromstring((caf_without_signature + "</CAF>").encode("ascii")).find("DA")
        canonical = etree.tostring(da, method="c14n", exclusive=False, with_comments=False)
        canonical = re.sub(rb">\s+<", b"><", canonical.decode("utf-8").encode("iso-8859-1"))
        signature = sii_signing_key.sign(canonical, padding.PKCS1v15(), hashes.SHA1())

    return (
        '<?xml version="1.0" encoding="ISO-8859-1"?>'
        "<AUTORIZACION>"
        f'{caf_without_signature}<FRMA algoritmo="SHA1withRSA">'
        f"{base64.b64encode(signature).decode()}</FRMA></CAF>"
        f"<RSASK>{private}</RSASK></AUTORIZACION>"
    ).encode("ascii")


def make_signing_credential(*, key_size: int = 2048) -> SigningCredential:
    key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CERTIFICADO SINTETICO")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    return SigningCredential(certificate=certificate, private_key=key)


def make_trusted_caf(**caf_kwargs) -> TrustedCafAuthorization:
    sii = make_signing_credential(key_size=1024)
    key_id = caf_kwargs.get("key_id", 100)
    payload = make_synthetic_caf(**caf_kwargs, sii_signing_key=sii.private_key)
    store = SiiCertificateStore()
    store.add(key_id, sii.certificate.public_bytes(serialization.Encoding.DER))
    return CafAuthenticityValidator(store).validate(CafLoader().load(payload))
