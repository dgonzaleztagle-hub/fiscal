"""Codec SOAP puro para Registro Reclamo DTE; no realiza conexiones de red."""

from dataclasses import dataclass
from lxml import etree

from completo_dte.domain import normalize_rut

SOAP = "http://schemas.xmlsoap.org/soap/envelope/"


class ReceivedRegistryCodecError(ValueError):
    """La solicitud o respuesta del WS no respeta el contrato fijado."""


@dataclass(frozen=True)
class RegistryResponse:
    code: int
    message: str

    @property
    def successful(self) -> bool:
        return self.code in {0, 1, 7}


class ReceivedRegistrySoapCodec:
    """Construye cuerpos sin endpoint, autenticación, cookies ni certificado."""

    def action_request(
        self, *, issuer_rut: str, document_type: int, folio: int, action_code: str
    ) -> bytes:
        if document_type not in {33, 34, 43}:
            raise ReceivedRegistryCodecError(
                "El WS oficial sólo admite DTE 33, 34 y 43"
            )
        if folio <= 0 or action_code not in {"ACD", "ERM", "RCD", "RFP", "RFT"}:
            raise ReceivedRegistryCodecError("Folio o acción de registro inválida")
        body, operation = _operation("ingresarAceptacionReclamoDoc")
        rut, dv = _split_rut(issuer_rut)
        for name, value in (
            ("rutEmisor", rut),
            ("dvEmisor", dv),
            ("tipoDoc", str(document_type)),
            ("folio", str(folio)),
            ("accionDoc", action_code),
        ):
            etree.SubElement(operation, name).text = value
        return _serialize(body)

    def events_request(
        self, *, issuer_rut: str, document_type: int, folio: int
    ) -> bytes:
        return self._identity_request(
            "listarEventosHistDoc", issuer_rut, document_type, folio
        )

    def reception_date_request(
        self, *, issuer_rut: str, document_type: int, folio: int
    ) -> bytes:
        return self._identity_request(
            "consultarFechaRecepcionSii", issuer_rut, document_type, folio
        )

    def parse_action_response(self, payload: bytes) -> RegistryResponse:
        root = _parse(payload)
        code = _unique_text(root, {"codResp", "codigo", "CodigoRespuesta"})
        message = _unique_text(
            root, {"descResp", "descripcion", "DescripcionRespuesta"}
        )
        try:
            return RegistryResponse(int(code), message)
        except ValueError as exc:
            raise ReceivedRegistryCodecError("Código SOAP no numérico") from exc

    def parse_reception_date(self, payload: bytes) -> str:
        root = _parse(payload)
        return _unique_text(
            root, {"fechaRecepcionSii", "fechaRecepcion", "FechaRecepcionSii"}
        )

    def _identity_request(self, method, issuer_rut, document_type, folio) -> bytes:
        if document_type not in {33, 34, 43} or folio <= 0:
            raise ReceivedRegistryCodecError("Identidad DTE no admitida por el WS")
        body, operation = _operation(method)
        rut, dv = _split_rut(issuer_rut)
        for name, value in (
            ("rutEmisor", rut),
            ("dvEmisor", dv),
            ("tipoDoc", str(document_type)),
            ("folio", str(folio)),
        ):
            etree.SubElement(operation, name).text = value
        return _serialize(body)


def _operation(name: str):
    envelope = etree.Element(etree.QName(SOAP, "Envelope"), nsmap={"soapenv": SOAP})
    body = etree.SubElement(envelope, etree.QName(SOAP, "Body"))
    operation = etree.SubElement(body, name)
    return envelope, operation


def _serialize(root) -> bytes:
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def _parse(payload: bytes):
    try:
        return etree.fromstring(
            payload,
            etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False),
        )
    except etree.XMLSyntaxError as exc:
        raise ReceivedRegistryCodecError("Respuesta SOAP inválida") from exc


def _split_rut(value: str) -> tuple[str, str]:
    normalized = normalize_rut(value)
    body, dv = normalized.split("-")
    return body, dv


def _unique_text(root, names: set[str]) -> str:
    values = [
        str(node.text).strip()
        for node in root.iter()
        if etree.QName(node).localname in names and node.text and node.text.strip()
    ]
    if len(values) != 1:
        raise ReceivedRegistryCodecError("Respuesta SOAP ambigua o incompleta")
    return values[0]
