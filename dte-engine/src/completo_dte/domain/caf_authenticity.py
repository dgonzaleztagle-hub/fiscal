"""Verificación de la firma del SII incluida en un CAF."""

import re
from dataclasses import dataclass

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree

from .caf import CafAuthorization, CafError


class CafTrustError(CafError):
    """No existe confianza explícita para el certificado indicado por el CAF."""


@dataclass(frozen=True)
class TrustedCafAuthorization:
    """CAF cuya firma FRMA ya fue verificada contra un certificado SII fijado."""

    authorization: CafAuthorization

    @property
    def data(self):
        return self.authorization.data

    @property
    def caf_xml(self) -> bytes:
        return self.authorization.caf_xml

    @property
    def private_key(self) -> rsa.RSAPrivateKey:
        return self.authorization.private_key


class SiiCertificateStore:
    """Certificados históricos del SII fijados explícitamente por IDK."""

    def __init__(self) -> None:
        self._certificates: dict[int, x509.Certificate] = {}

    def add(
        self,
        key_id: int,
        certificate_bytes: bytes,
        *,
        expected_sha256: str | None = None,
    ) -> None:
        certificate = _load_certificate(certificate_bytes)
        if not isinstance(certificate.public_key(), rsa.RSAPublicKey):
            raise CafTrustError("El certificado SII debe contener una clave RSA")
        fingerprint = certificate.fingerprint(hashes.SHA256()).hex().upper()
        if (
            expected_sha256 is not None
            and fingerprint != expected_sha256.replace(":", "").upper()
        ):
            raise CafTrustError("El fingerprint del certificado SII no coincide")
        existing = self._certificates.get(key_id)
        if existing is not None and existing.fingerprint(
            hashes.SHA256()
        ) != certificate.fingerprint(hashes.SHA256()):
            raise CafTrustError(f"IDK {key_id} ya está asociado a otro certificado")
        self._certificates[key_id] = certificate

    def get(self, key_id: int) -> x509.Certificate:
        try:
            return self._certificates[key_id]
        except KeyError as exc:
            raise CafTrustError(
                f"No existe un certificado SII confiable para IDK {key_id}"
            ) from exc


class CafAuthenticityValidator:
    def __init__(self, certificates: SiiCertificateStore) -> None:
        self._certificates = certificates

    def validate(self, caf: CafAuthorization) -> TrustedCafAuthorization:
        certificate = self._certificates.get(caf.data.key_id)
        public_key = certificate.public_key()
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise CafTrustError("El certificado SII no usa RSA")

        try:
            root = etree.fromstring(
                caf.caf_xml,
                etree.XMLParser(
                    resolve_entities=False, no_network=True, remove_blank_text=False
                ),
            )
        except etree.XMLSyntaxError as exc:
            raise CafError(
                "No fue posible interpretar el bloque CAF para validar FRMA"
            ) from exc
        da = root.find("DA")
        frma = root.find("FRMA")
        if da is None or frma is None or not frma.text:
            raise CafError("El CAF no contiene DA y FRMA")
        if frma.get("algoritmo") != "SHA1withRSA":
            raise CafError("El algoritmo FRMA del CAF no está soportado")

        signed_data = canonicalize_caf_da(da)
        try:
            public_key.verify(
                caf.sii_signature,
                signed_data,
                padding.PKCS1v15(),
                hashes.SHA1(),  # noqa: S303 - algoritmo obligatorio del CAF SII.
            )
        except InvalidSignature as exc:
            raise CafError(
                "La firma FRMA del CAF no es válida para el certificado SII"
            ) from exc
        return TrustedCafAuthorization(caf)


def canonicalize_caf_da(da: etree._Element) -> bytes:
    """Canonicaliza DA con la codificación histórica usada por el protocolo SII."""
    utf8 = etree.tostring(da, method="c14n", exclusive=False, with_comments=False)
    text = utf8.decode("utf-8")
    text = _escape_quotes_in_text_nodes(text)
    encoded = text.encode("iso-8859-1")
    return re.sub(rb">\s+<", b"><", encoded)


def _escape_quotes_in_text_nodes(xml: str) -> str:
    pieces = re.split(r"(<[^>]+>)", xml)
    return "".join(
        piece
        if piece.startswith("<")
        else piece.replace("'", "&apos;").replace('"', "&quot;")
        for piece in pieces
    )


def _load_certificate(payload: bytes) -> x509.Certificate:
    try:
        if b"-----BEGIN CERTIFICATE-----" in payload:
            return x509.load_pem_x509_certificate(payload)
        return x509.load_der_x509_certificate(payload)
    except ValueError as exc:
        raise CafTrustError("El certificado SII no es X.509 válido") from exc
