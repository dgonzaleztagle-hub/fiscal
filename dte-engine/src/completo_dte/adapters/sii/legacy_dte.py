"""Gateway DTE heredado usado por el RCOF y otros sobres no cubiertos por REST."""

from dataclasses import dataclass
from html import unescape
from time import monotonic

import httpx
from lxml import etree

from completo_dte.domain import SigningCredential
from .boleta_api import (
    EnvelopeOutcome,
    SeedSigner,
    SiiApiError,
    _rut_parts,
    classify_envelope_status,
)


@dataclass(frozen=True)
class LegacyUploadReceipt:
    track_id: str
    status: str
    received_at: str | None


@dataclass(frozen=True)
class LegacyEnvelopeStatus:
    track_id: str
    status: str
    reported: int
    accepted: int
    rejected: int
    repairs: int

    @property
    def outcome(self) -> EnvelopeOutcome:
        return classify_envelope_status(
            self.status,
            ({"rechazados": self.rejected, "reparos": self.repairs},),
        )


class SiiLegacyDteApi:
    """SOAP mínimo para token + multipart DTE, sin reintentos implícitos."""

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
        host = "maullin.sii.cl" if environment == "certification" else "palena.sii.cl"
        self._base = f"https://{host}"
        self._credential = credential
        self._client = client or httpx.Client(timeout=30, follow_redirects=False)
        self._user_agent = user_agent
        self._token: str | None = None
        self._token_at = 0.0

    def authenticate(self, *, force: bool = False) -> str:
        if not force and self._token and monotonic() - self._token_at < 3300:
            return self._token
        seed_response = self._soap("CrSeed", "getSeed")
        seed = _inner_value(seed_response, "SEMILLA")
        if _inner_value(seed_response, "ESTADO") not in {"0", "00"}:
            raise SiiApiError("El SII rechazó la semilla DTE")
        signed = SeedSigner().sign(seed, self._credential)
        token_response = self._soap(
            "GetTokenFromSeed",
            "getToken",
            parameter=("pszXml", signed.decode("ISO-8859-1")),
        )
        if _inner_value(token_response, "ESTADO") not in {"0", "00"}:
            raise SiiApiError("El SII rechazó la autenticación DTE")
        token = _inner_value(token_response, "TOKEN")
        if not token or len(token) > 500:
            raise SiiApiError("El SII entregó un token DTE inválido")
        self._token = token
        self._token_at = monotonic()
        return token

    def upload(
        self,
        xml: bytes,
        *,
        issuer_rut: str,
        sender_rut: str,
        filename: str,
    ) -> LegacyUploadReceipt:
        if not xml:
            raise SiiApiError("No se puede enviar un XML vacío")
        issuer_body, issuer_dv = _rut_parts(issuer_rut)
        sender_body, sender_dv = _rut_parts(sender_rut)
        response = self._client.post(
            f"{self._base}/cgi_dte/UPL/DTEUpload",
            data={
                "rutSender": sender_body,
                "dvSender": sender_dv,
                "rutCompany": issuer_body,
                "dvCompany": issuer_dv,
            },
            files={"archivo": (filename, xml, "application/xml")},
            headers={
                "Cookie": f"TOKEN={self.authenticate()}",
                "User-Agent": self._user_agent,
            },
        )
        if response.status_code == 401:
            self.authenticate(force=True)
            raise SiiApiError("Token DTE rechazado; se requiere reintento controlado")
        if not 200 <= response.status_code < 300:
            raise SiiApiError(f"Upload DTE falló; HTTP {response.status_code}")
        status = _xml_value(response.content, "STATUS")
        if status not in {"0", "00"}:
            raise SiiApiError(f"El SII rechazó el upload DTE con estado {status}")
        return LegacyUploadReceipt(
            track_id=_xml_value(response.content, "TRACKID"),
            status=status,
            received_at=_xml_optional(response.content, "TMST"),
        )

    def get_upload_status(
        self,
        *,
        issuer_rut: str,
        track_id: str,
    ) -> LegacyEnvelopeStatus:
        token = str(track_id).strip()
        if not token.isdigit() or not 1 <= len(token) <= 30:
            raise SiiApiError("El Track ID DTE no tiene un formato válido")
        rut, dv = _rut_parts(issuer_rut)
        response = self._soap(
            "QueryEstUp",
            "getEstUp",
            parameters=(
                ("RutCompania", rut),
                ("DvCompania", dv),
                ("TrackId", token),
                ("Token", self.authenticate()),
            ),
        )
        inner = _inner_payload(response)
        returned_track = _xml_optional(inner, "TRACKID")
        if returned_track is not None and returned_track != token:
            raise SiiApiError("La respuesta DTE no corresponde al Track ID consultado")
        return LegacyEnvelopeStatus(
            track_id=token,
            status=_xml_value(inner, "ESTADO"),
            reported=_xml_integer_sum(inner, "INFORMADOS"),
            accepted=_xml_integer_sum(inner, "ACEPTADOS"),
            rejected=_xml_integer_sum(inner, "RECHAZADOS"),
            repairs=_xml_integer_sum(inner, "REPAROS"),
        )

    def _soap(
        self,
        service: str,
        method: str,
        *,
        parameter: tuple[str, str] | None = None,
        parameters: tuple[tuple[str, str], ...] | None = None,
    ) -> bytes:
        ns = f"{self._base}/DTEWS/{service}.jws"
        envelope = etree.Element(
            "{http://schemas.xmlsoap.org/soap/envelope/}Envelope",
            nsmap={"soapenv": "http://schemas.xmlsoap.org/soap/envelope/"},
        )
        body = etree.SubElement(
            envelope, "{http://schemas.xmlsoap.org/soap/envelope/}Body"
        )
        call = etree.SubElement(body, etree.QName(ns, method))
        if parameter and parameters:
            raise ValueError("Use parameter o parameters, no ambos")
        for name, value in parameters or ((parameter,) if parameter else ()):
            etree.SubElement(call, name).text = value
        response = self._client.post(
            f"{self._base}/DTEWS/{service}.jws",
            content=etree.tostring(envelope, encoding="utf-8", xml_declaration=True),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "",
                "User-Agent": self._user_agent,
            },
        )
        if not 200 <= response.status_code < 300:
            raise SiiApiError(
                f"Servicio SOAP {service}.{method} falló; HTTP {response.status_code}"
            )
        return response.content


def _inner_value(soap_payload: bytes, name: str) -> str:
    return _xml_value(_inner_payload(soap_payload), name)


def _inner_payload(soap_payload: bytes) -> bytes:
    try:
        root = etree.fromstring(
            soap_payload, etree.XMLParser(resolve_entities=False, no_network=True)
        )
    except etree.XMLSyntaxError as exc:
        raise SiiApiError("El SII respondió SOAP inválido") from exc
    returns = root.xpath("//*[contains(local-name(), 'Return')]/text()")
    if not returns:
        raise SiiApiError("Respuesta SOAP sin contenido")
    return unescape(str(returns[0])).encode("utf-8")


def _xml_value(payload: bytes, name: str) -> str:
    value = _xml_optional(payload, name)
    if not value:
        raise SiiApiError(f"Respuesta SII sin {name}")
    return value


def _xml_optional(payload: bytes, name: str) -> str | None:
    try:
        root = etree.fromstring(
            payload, etree.XMLParser(resolve_entities=False, no_network=True)
        )
    except etree.XMLSyntaxError as exc:
        raise SiiApiError("El SII respondió XML inválido") from exc
    values = root.xpath(f"//*[local-name()='{name}']/text()")
    return str(values[0]).strip() if values and str(values[0]).strip() else None


def _xml_integer_sum(payload: bytes, name: str) -> int:
    try:
        root = etree.fromstring(
            payload, etree.XMLParser(resolve_entities=False, no_network=True)
        )
    except etree.XMLSyntaxError as exc:
        raise SiiApiError("El SII respondió XML inválido") from exc
    total = 0
    for value in root.xpath(f"//*[local-name()='{name}']/text()"):
        try:
            parsed = int(str(value).strip())
        except ValueError as exc:
            raise SiiApiError(f"Respuesta SII con {name} inválido") from exc
        if parsed < 0:
            raise SiiApiError(f"Respuesta SII con {name} negativo")
        total += parsed
    return total
