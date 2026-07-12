"""API REST oficial para autenticación, envío y estado de boletas."""

import base64
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
import hashlib
import json
from time import monotonic

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import Encoding
import httpx
from lxml import etree

from completo_dte.domain import SigningCredential, normalize_rut
from completo_dte.domain.xml_signature import C14N, DS, RSA_SHA1, SHA1


class SiiApiError(RuntimeError):
    """La API del SII no respondió con un resultado utilizable."""


class EnvelopeOutcome(str, Enum):
    PROCESSING = "processing"
    ACCEPTED = "accepted"
    ACCEPTED_WITH_OBJECTIONS = "accepted_with_objections"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class UploadReceipt:
    issuer_rut: str
    sender_rut: str
    track_id: str
    received_at: str
    status: str
    filename: str


@dataclass(frozen=True)
class RemoteEnvelopeStatus:
    track_id: str
    status: str
    issuer_rut: str
    sender_rut: str
    received_at: str
    statistics: tuple[dict, ...]
    details: tuple[dict, ...]

    @property
    def outcome(self) -> EnvelopeOutcome:
        return classify_envelope_status(self.status, self.statistics, self.details)


class SeedSigner:
    """Firma el `getToken` con Reference URI vacío y transform enveloped."""

    def sign(self, seed: str, credential: SigningCredential) -> bytes:
        if not seed.isdigit() or not 1 <= len(seed) <= 20:
            raise SiiApiError("La semilla del SII no tiene un formato válido")
        root = etree.Element("getToken")
        item = etree.SubElement(root, "item")
        etree.SubElement(item, "Semilla").text = seed

        digest = hashlib.sha1(_canonicalize(root)).digest()  # noqa: S324 - XMLDSig SII.
        signature = etree.Element(etree.QName(DS, "Signature"), nsmap={None: DS})
        signed_info = etree.SubElement(signature, etree.QName(DS, "SignedInfo"))
        etree.SubElement(
            signed_info,
            etree.QName(DS, "CanonicalizationMethod"),
            Algorithm=C14N,
        )
        etree.SubElement(
            signed_info,
            etree.QName(DS, "SignatureMethod"),
            Algorithm=RSA_SHA1,
        )
        reference = etree.SubElement(
            signed_info,
            etree.QName(DS, "Reference"),
            URI="",
        )
        transforms = etree.SubElement(reference, etree.QName(DS, "Transforms"))
        etree.SubElement(
            transforms,
            etree.QName(DS, "Transform"),
            Algorithm=f"{DS}enveloped-signature",
        )
        etree.SubElement(reference, etree.QName(DS, "DigestMethod"), Algorithm=SHA1)
        etree.SubElement(reference, etree.QName(DS, "DigestValue")).text = base64.b64encode(
            digest
        ).decode("ascii")
        signature_value = credential.private_key.sign(
            _canonicalize(signed_info),
            padding.PKCS1v15(),
            hashes.SHA1(),  # noqa: S303 - algoritmo obligatorio de XMLDSig SII.
        )
        etree.SubElement(signature, etree.QName(DS, "SignatureValue")).text = (
            base64.b64encode(signature_value).decode("ascii")
        )
        key_info = etree.SubElement(signature, etree.QName(DS, "KeyInfo"))
        key_value = etree.SubElement(key_info, etree.QName(DS, "KeyValue"))
        rsa_key = etree.SubElement(key_value, etree.QName(DS, "RSAKeyValue"))
        numbers = credential.private_key.public_key().public_numbers()
        etree.SubElement(rsa_key, etree.QName(DS, "Modulus")).text = _integer_base64(numbers.n)
        etree.SubElement(rsa_key, etree.QName(DS, "Exponent")).text = _integer_base64(numbers.e)
        x509_data = etree.SubElement(key_info, etree.QName(DS, "X509Data"))
        etree.SubElement(x509_data, etree.QName(DS, "X509Certificate")).text = (
            base64.b64encode(
                credential.certificate.public_bytes(Encoding.DER)
            ).decode("ascii")
        )
        root.append(signature)
        return etree.tostring(
            root,
            encoding="ISO-8859-1",
            xml_declaration=True,
            pretty_print=False,
        )


class SiiBoletaApi:
    CERT_API = "https://apicert.sii.cl/recursos/v1"
    CERT_UPLOAD_API = "https://pangal.sii.cl/recursos/v1"
    PROD_API = "https://api.sii.cl/recursos/v1"
    PROD_UPLOAD_API = "https://rahue.sii.cl/recursos/v1"

    def __init__(
        self,
        credential: SigningCredential,
        *,
        environment: str = "certification",
        client: httpx.Client | None = None,
        user_agent: str = "Completo-DTE/0.1",
    ) -> None:
        if environment not in ("certification", "production"):
            raise ValueError("Ambiente SII inválido")
        self._credential = credential
        self._base_url = self.CERT_API if environment == "certification" else self.PROD_API
        self._upload_url = (
            self.CERT_UPLOAD_API if environment == "certification" else self.PROD_UPLOAD_API
        )
        self._client = client or httpx.Client(timeout=30, follow_redirects=False)
        self._user_agent = user_agent
        self._token: str | None = None
        self._token_obtained_at = 0.0

    def authenticate(self, *, force: bool = False) -> str:
        if (
            not force
            and self._token is not None
            and monotonic() - self._token_obtained_at < timedelta(minutes=55).total_seconds()
        ):
            return self._token
        seed_response = self._client.get(
            f"{self._base_url}/boleta.electronica.semilla",
            headers={"User-Agent": self._user_agent},
        )
        _require_success(seed_response, "obtener semilla")
        seed = _xml_value(seed_response.content, "SEMILLA")
        if _xml_value(seed_response.content, "ESTADO") not in ("0", "00"):
            raise SiiApiError("El SII rechazó la solicitud de semilla")

        signed_seed = SeedSigner().sign(seed, self._credential)
        token_response = self._client.post(
            f"{self._base_url}/boleta.electronica.token",
            content=signed_seed,
            headers={
                "Content-Type": "application/xml",
                "User-Agent": self._user_agent,
            },
        )
        _require_success(token_response, "obtener token")
        if _xml_value(token_response.content, "ESTADO") not in ("0", "00"):
            glosa = _xml_optional_value(token_response.content, "GLOSA")
            raise SiiApiError(f"El SII rechazó la autenticación: {glosa or 'sin detalle'}")
        token = _xml_value(token_response.content, "TOKEN")
        if not 1 <= len(token) <= 500:
            raise SiiApiError("El SII entregó un token inválido")
        self._token = token
        self._token_obtained_at = monotonic()
        return token

    def upload_boletas(
        self,
        xml: bytes,
        *,
        issuer_rut: str,
        sender_rut: str,
        filename: str,
    ) -> UploadReceipt:
        if not xml:
            raise SiiApiError("No se puede enviar un sobre vacío")
        if not filename or len(filename) > 200 or any(c in filename for c in "\\/\r\n"):
            raise SiiApiError("El nombre del archivo de envío no es válido")
        normalized_issuer = normalize_rut(issuer_rut)
        normalized_sender = normalize_rut(sender_rut)
        issuer_body, issuer_dv = _rut_parts(normalized_issuer)
        sender_body, sender_dv = _rut_parts(normalized_sender)
        token = self.authenticate()
        response = self._client.post(
            f"{self._upload_url}/boleta.electronica.envio",
            data={
                "rutSender": sender_body,
                "dvSender": sender_dv,
                "rutCompany": issuer_body,
                "dvCompany": issuer_dv,
            },
            files={"archivo": (filename, xml, "application/xml")},
            headers={
                "Cookie": f"TOKEN={token}",
                "User-Agent": self._user_agent,
            },
        )
        if response.status_code == 401:
            self.authenticate(force=True)
            raise SiiApiError("Token rechazado por el SII; reintento controlado requerido")
        _require_success(response, "enviar boletas")
        data = _json_object(response)
        response_issuer = _normalized_response_rut(data, "rut_emisor")
        response_sender = _normalized_response_rut(data, "rut_envia")
        track_id = _required_numeric_field(data, "trackid", maximum_length=30)
        if response_issuer != normalized_issuer or response_sender != normalized_sender:
            raise SiiApiError("La respuesta del SII no corresponde al emisor o enviador solicitado")
        return UploadReceipt(
            issuer_rut=response_issuer,
            sender_rut=response_sender,
            track_id=track_id,
            received_at=_required_string_field(data, "fecha_recepcion"),
            status=_required_string_field(data, "estado"),
            filename=_required_string_field(data, "file"),
        )

    def get_envelope_status(
        self,
        *,
        issuer_rut: str,
        track_id: str,
    ) -> RemoteEnvelopeStatus:
        normalized_issuer = normalize_rut(issuer_rut)
        track_id = _validated_track_id(track_id)
        body, dv = _rut_parts(normalized_issuer)
        token = self.authenticate()
        response = self._client.get(
            f"{self._base_url}/boleta.electronica.envio/{body}-{dv}-{track_id}",
            headers={
                "Cookie": f"TOKEN={token}",
                "User-Agent": self._user_agent,
            },
        )
        _require_success(response, "consultar estado del envío")
        data = _json_object(response)
        response_track_id = _required_numeric_field(data, "trackid", maximum_length=30)
        response_issuer = _normalized_response_rut(data, "rut_emisor")
        if response_track_id != track_id or response_issuer != normalized_issuer:
            raise SiiApiError("La respuesta de estado del SII no corresponde a la consulta")
        return RemoteEnvelopeStatus(
            track_id=response_track_id,
            status=_required_string_field(data, "estado"),
            issuer_rut=response_issuer,
            sender_rut=_normalized_response_rut(data, "rut_envia"),
            received_at=_required_string_field(data, "fecha_recepcion"),
            statistics=_dict_tuple(data, "estadistica"),
            details=_dict_tuple(data, "detalle_rep_rech"),
        )


def _rut_parts(value: str) -> tuple[str, str]:
    normalized = normalize_rut(value)
    body, dv = normalized.split("-")
    return body, dv


def classify_envelope_status(
    status: str,
    statistics: tuple[dict, ...] = (),
    details: tuple[dict, ...] = (),
) -> EnvelopeOutcome:
    """Reduce códigos SII a estados operativos sin adivinar códigos desconocidos."""
    code = status.strip().upper()
    if code in {"RSC", "RCH", "RPT", "RFR", "VOF", "RCT"}:
        return EnvelopeOutcome.REJECTED
    if code in {"RLV", "RPR"}:
        return EnvelopeOutcome.ACCEPTED_WITH_OBJECTIONS
    if code == "EPR":
        rejected = sum(_integer_field(row, "rechazados", "rechazado") for row in statistics)
        objections = sum(
            _integer_field(row, "reparos", "reparo") for row in statistics
        )
        if rejected:
            return EnvelopeOutcome.REJECTED
        if objections or details:
            return EnvelopeOutcome.ACCEPTED_WITH_OBJECTIONS
        return EnvelopeOutcome.ACCEPTED
    if code in {
        "001", "002", "003", "004", "005", "007", "106", "107",
        "-11", "-8", "REC", "SOK", "FOK", "PDR", "PRD", "CRT",
    }:
        return EnvelopeOutcome.PROCESSING
    return EnvelopeOutcome.UNKNOWN


def _integer_field(row: dict, *names: str) -> int:
    for name in names:
        value = row.get(name)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    return 0


def _xml_value(payload: bytes, local_name: str) -> str:
    value = _xml_optional_value(payload, local_name)
    if value is None or not value.strip():
        raise SiiApiError(f"Respuesta SII sin {local_name}")
    return value.strip()


def _xml_optional_value(payload: bytes, local_name: str) -> str | None:
    try:
        root = etree.fromstring(
            payload,
            etree.XMLParser(resolve_entities=False, no_network=True),
        )
    except etree.XMLSyntaxError as exc:
        raise SiiApiError("El SII respondió XML inválido") from exc
    values = root.xpath(f"//*[local-name()='{local_name}']/text()")
    return str(values[0]) if values else None


def _json_object(response: httpx.Response) -> dict:
    try:
        value = response.json()
    except json.JSONDecodeError as exc:
        raise SiiApiError("El SII respondió JSON inválido") from exc
    if not isinstance(value, dict):
        raise SiiApiError("El SII respondió un objeto inesperado")
    return value


def _required_string_field(data: dict, name: str) -> str:
    value = data.get(name)
    if value is None or not str(value).strip():
        raise SiiApiError(f"Respuesta SII sin {name}")
    return str(value).strip()


def _required_numeric_field(data: dict, name: str, *, maximum_length: int) -> str:
    return _validated_numeric_token(
        _required_string_field(data, name),
        name,
        maximum_length=maximum_length,
    )


def _validated_track_id(value: str) -> str:
    return _validated_numeric_token(value, "track_id", maximum_length=30)


def _validated_numeric_token(value: str, label: str, *, maximum_length: int) -> str:
    token = str(value).strip()
    if not token.isdigit() or not 1 <= len(token) <= maximum_length:
        raise SiiApiError(f"{label} no tiene un formato válido")
    return token


def _normalized_response_rut(data: dict, name: str) -> str:
    try:
        return normalize_rut(_required_string_field(data, name))
    except ValueError as exc:
        raise SiiApiError(f"Respuesta SII con {name} inválido") from exc


def _dict_tuple(data: dict, name: str) -> tuple[dict, ...]:
    value = data.get(name) or ()
    if not isinstance(value, (list, tuple)) or any(not isinstance(row, dict) for row in value):
        raise SiiApiError(f"Respuesta SII con {name} inválido")
    return tuple(value)


def _require_success(response: httpx.Response, action: str) -> None:
    if 200 <= response.status_code < 300:
        return
    raise SiiApiError(f"No fue posible {action}; HTTP {response.status_code}")


def _canonicalize(element: etree._Element) -> bytes:
    return etree.tostring(element, method="c14n", exclusive=False, with_comments=False)


def _integer_base64(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.b64encode(raw).decode("ascii")
