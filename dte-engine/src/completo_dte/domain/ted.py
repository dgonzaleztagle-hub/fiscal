"""Construcción y firma del Timbre Electrónico del DTE."""

import base64
from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Protocol
from zoneinfo import ZoneInfo

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from .caf_authenticity import TrustedCafAuthorization


class TedError(ValueError):
    """No fue posible construir un TED consistente."""


class TedDocument(Protocol):
    issuer_rut: str
    document_type: int
    folio: int
    issued_on: object
    receiver_rut: str
    receiver_name: str
    total: int
    lines: tuple


@dataclass(frozen=True)
class SignedTed:
    xml: bytes
    dd: bytes
    signature: bytes

    def verify(self, caf: TrustedCafAuthorization) -> bool:
        try:
            caf.private_key.public_key().verify(
                self.signature,
                self.dd,
                padding.PKCS1v15(),
                hashes.SHA1(),  # noqa: S303 - algoritmo obligatorio del TED SII.
            )
            return True
        except InvalidSignature:
            return False


class TedBuilder:
    def build(
        self,
        boleta: TedDocument,
        caf: TrustedCafAuthorization,
        *,
        generated_at: datetime,
    ) -> SignedTed:
        if not isinstance(caf, TrustedCafAuthorization):
            raise TedError("El CAF debe tener su firma FRMA validada antes de timbrar")
        self._assert_caf_applies(boleta, caf)
        timestamp = _sii_local_timestamp(generated_at)
        first_item = _latin1_prefix(boleta.lines[0].name, 40)

        fields = (
            _element("RE", boleta.issuer_rut)
            + _element("TD", str(boleta.document_type))
            + _element("F", str(boleta.folio))
            + _element("FE", boleta.issued_on.isoformat())
            + _element("RR", boleta.receiver_rut)
            + _element("RSR", boleta.receiver_name)
            + _element("MNT", str(boleta.total))
            + _element("IT1", first_item)
        )
        dd = b"<DD>" + fields + caf.caf_xml + _element("TSTED", timestamp) + b"</DD>"
        signature = caf.private_key.sign(
            dd,
            padding.PKCS1v15(),
            hashes.SHA1(),  # noqa: S303
        )
        encoded_signature = base64.b64encode(signature)
        xml = (
            b'<TED version="1.0">'
            + dd
            + b'<FRMT algoritmo="SHA1withRSA">'
            + encoded_signature
            + b"</FRMT></TED>"
        )
        return SignedTed(xml=xml, dd=dd, signature=signature)

    @staticmethod
    def _assert_caf_applies(
        boleta: TedDocument,
        caf: TrustedCafAuthorization,
    ) -> None:
        data = caf.data
        if data.issuer_rut != boleta.issuer_rut:
            raise TedError("El CAF pertenece a otro emisor")
        if data.document_type != boleta.document_type:
            raise TedError(f"El CAF no autoriza documentos tipo {boleta.document_type}")
        if not data.folio_from <= boleta.folio <= data.folio_to:
            raise TedError("El folio está fuera del rango autorizado por el CAF")


def _element(tag: str, value: str) -> bytes:
    try:
        encoded = escape(value, quote=False).encode("iso-8859-1")
    except UnicodeEncodeError as exc:
        raise TedError(f"{tag} contiene caracteres fuera de ISO-8859-1") from exc
    return (
        b"<" + tag.encode("ascii") + b">" + encoded + b"</" + tag.encode("ascii") + b">"
    )


def _latin1_prefix(value: str, maximum_bytes: int) -> str:
    try:
        encoded = value.encode("iso-8859-1")
    except UnicodeEncodeError as exc:
        raise TedError(
            "El primer ítem contiene caracteres fuera de ISO-8859-1"
        ) from exc
    return encoded[:maximum_bytes].decode("iso-8859-1")


def _sii_local_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise TedError("generated_at debe incluir zona horaria")
    local = value.astimezone(ZoneInfo("America/Santiago"))
    return local.strftime("%Y-%m-%dT%H:%M:%S")
