"""Carga defensiva de Códigos de Autorización de Folios (CAF)."""

from dataclasses import dataclass
from datetime import date
import re

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from lxml import etree

from .rut import RutError, normalize_rut


class CafError(ValueError):
    """El CAF no cumple las invariantes locales mínimas."""


@dataclass(frozen=True)
class CafData:
    issuer_rut: str
    issuer_name: str
    document_type: int
    folio_from: int
    folio_to: int
    authorization_date: date
    key_id: int


@dataclass(frozen=True)
class CafAuthorization:
    data: CafData
    caf_xml: bytes
    sii_signature: bytes
    private_key: rsa.RSAPrivateKey


class CafLoader:
    """Extrae y valida estructura, rango, RUT y par de claves de un CAF."""

    def load(self, xml: bytes) -> CafAuthorization:
        if not xml or len(xml) > 1_000_000:
            raise CafError("El CAF está vacío o excede el tamaño máximo permitido")
        try:
            parser = etree.XMLParser(
                resolve_entities=False,
                no_network=True,
                load_dtd=False,
                huge_tree=False,
            )
            root = etree.fromstring(xml, parser=parser)
        except etree.XMLSyntaxError as exc:
            raise CafError("El CAF no es XML válido") from exc

        authorization = (
            root if root.tag == "AUTORIZACION" else root.find(".//AUTORIZACION")
        )
        if authorization is None:
            raise CafError("Falta AUTORIZACION")

        caf = authorization.find("CAF")
        da = caf.find("DA") if caf is not None else None
        if caf is None or da is None:
            raise CafError("Falta CAF/DA")
        if caf.get("version") != "1.0":
            raise CafError("Solo se admite CAF versión 1.0")

        try:
            issuer_rut = normalize_rut(_required_text(da, "RE"))
            issuer_name = _required_text(da, "RS")
            document_type = int(_required_text(da, "TD"))
            folio_from = int(_required_text(da, "RNG/D"))
            folio_to = int(_required_text(da, "RNG/H"))
            authorization_date = date.fromisoformat(_required_text(da, "FA"))
            key_id = int(_required_text(da, "IDK"))
        except (RutError, ValueError) as exc:
            raise CafError(f"Datos de CAF inválidos: {exc}") from exc

        if document_type not in {33, 34, 39, 41, 52, 56, 61}:
            raise CafError(f"Tipo DTE no soportado: {document_type}")
        if folio_from <= 0 or folio_to < folio_from:
            raise CafError("Rango de folios inválido")
        if len(issuer_name) > 40:
            raise CafError("La razón social del CAF excede 40 caracteres")

        signature = _decode_base64(_required_text(caf, "FRMA"), "FRMA")
        private_key = _load_private_key(_required_text(authorization, "RSASK"))
        _assert_key_matches_caf(private_key, da)
        caf_xml = _extract_original_caf(xml)

        return CafAuthorization(
            data=CafData(
                issuer_rut=issuer_rut,
                issuer_name=issuer_name,
                document_type=document_type,
                folio_from=folio_from,
                folio_to=folio_to,
                authorization_date=authorization_date,
                key_id=key_id,
            ),
            caf_xml=caf_xml,
            sii_signature=signature,
            private_key=private_key,
        )


def _required_text(parent: etree._Element, path: str) -> str:
    element = parent.find(path)
    if element is None or not element.text or not element.text.strip():
        raise CafError(f"Falta campo obligatorio {path}")
    return element.text.strip()


def _decode_base64(value: str, field: str) -> bytes:
    import base64
    import binascii

    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise CafError(f"{field} no contiene Base64 válido") from exc


def _load_private_key(value: str) -> rsa.RSAPrivateKey:
    body = "".join(value.split())
    pem = f"-----BEGIN RSA PRIVATE KEY-----\n{body}\n-----END RSA PRIVATE KEY-----\n".encode()
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except (TypeError, ValueError) as exc:
        raise CafError("RSASK no contiene una clave privada RSA válida") from exc
    if not isinstance(key, rsa.RSAPrivateKey):
        raise CafError("RSASK no es una clave RSA")
    return key


def _assert_key_matches_caf(private_key: rsa.RSAPrivateKey, da: etree._Element) -> None:
    modulus = int.from_bytes(_decode_base64(_required_text(da, "RSAPK/M"), "RSAPK/M"))
    exponent = int.from_bytes(_decode_base64(_required_text(da, "RSAPK/E"), "RSAPK/E"))
    public_numbers = private_key.public_key().public_numbers()
    if public_numbers.n != modulus or public_numbers.e != exponent:
        raise CafError(
            "La clave privada RSASK no corresponde a la clave pública del CAF"
        )


def _extract_original_caf(xml: bytes) -> bytes:
    """Conserva el CAF byte a byte: el SII exige incluirlo sin modificaciones."""
    match = re.search(rb"<CAF\b[^>]*>.*?</CAF\s*>", xml, flags=re.DOTALL)
    if match is None:
        raise CafError("No fue posible conservar el bloque CAF original")
    return match.group(0)
