"""Construcción y firma de un sobre EnvioBOLETA."""

from dataclasses import dataclass
from datetime import date, datetime
from collections import Counter

from lxml import etree

from .certificate import SigningCredential
from .rut import normalize_rut
from .ted import _element, _sii_local_timestamp
from .xml_signature import SII, SignedDte, XmlSigner


@dataclass(frozen=True)
class EnvelopeAuthorization:
    resolution_date: date
    resolution_number: int

    def __post_init__(self) -> None:
        if not 0 <= self.resolution_number <= 999_999:
            raise ValueError("El número de resolución debe tener hasta 6 dígitos")


@dataclass(frozen=True)
class SignedEnvelope:
    xml: bytes
    set_id: str


class EnvioBoletaBuilder:
    SII_RUT = "60803000-K"

    def build(
        self,
        documents: tuple[SignedDte, ...],
        *,
        issuer_rut: str,
        sender_rut: str,
        authorization: EnvelopeAuthorization,
        signed_at: datetime,
        credential: SigningCredential,
        set_id: str = "SetDoc",
    ) -> SignedEnvelope:
        if not 1 <= len(documents) <= 500:
            raise ValueError("EnvioBOLETA debe contener entre 1 y 500 documentos")
        issuer_rut = normalize_rut(issuer_rut)
        sender_rut = normalize_rut(sender_rut)
        if not set_id or not set_id[0].isalpha() or not set_id.replace("_", "").isalnum():
            raise ValueError("set_id debe ser un ID XML simple")

        signer = XmlSigner()
        identities = []
        for document in documents:
            if not signer.verify_with_certificate(document, credential.certificate):
                raise ValueError(
                    "EnvioBOLETA contiene un DTE cuya firma no corresponde a la credencial"
                )
            document_issuer, document_type, folio = _document_identity(document)
            if document_issuer != issuer_rut:
                raise ValueError("EnvioBOLETA contiene un DTE de otro emisor")
            if document_type not in {39, 41}:
                raise ValueError("EnvioBOLETA sólo admite boletas tipo 39 o 41")
            identities.append((document.document_id, document_type, folio))
        if len(identities) != len(set(identities)):
            raise ValueError("EnvioBOLETA no puede repetir un mismo DTE")
        folios = [(document_type, folio) for _, document_type, folio in identities]
        if len(folios) != len(set(folios)):
            raise ValueError("EnvioBOLETA no puede repetir tipo y folio")

        counts = Counter(document_type for _, document_type, _ in identities)
        subtotals = b"".join(
            b"<SubTotDTE>"
            + _element("TpoDTE", str(document_type))
            + _element("NroDTE", str(count))
            + b"</SubTotDTE>"
            for document_type, count in sorted(counts.items())
        )
        caratula = (
            b'<Caratula version="1.0">'
            + _element("RutEmisor", issuer_rut)
            + _element("RutEnvia", sender_rut)
            + _element("RutReceptor", self.SII_RUT)
            + _element("FchResol", authorization.resolution_date.isoformat())
            + _element("NroResol", str(authorization.resolution_number))
            + _element("TmstFirmaEnv", _sii_local_timestamp(signed_at))
            + subtotals
            + b"</Caratula>"
        )
        embedded = b"".join(_without_declaration(document.xml) for document in documents)
        unsigned = (
            b'<?xml version="1.0" encoding="ISO-8859-1"?>'
            b'<EnvioBOLETA version="1.0" xmlns="http://www.sii.cl/SiiDte">'
            b'<SetDTE ID="'
            + set_id.encode("ascii")
            + b'">'
            + caratula
            + embedded
            + b"</SetDTE></EnvioBOLETA>"
        )
        signed = XmlSigner().sign_raw(
            unsigned,
            target_tag=f"{{{SII}}}SetDTE",
            target_id=set_id,
            credential=credential,
        )
        return SignedEnvelope(xml=signed, set_id=set_id)


class EnvioDteBuilder:
    """Sobre de facturas 33/34 dirigido al SII."""

    SII_RUT = "60803000-K"

    def build(
        self,
        documents: tuple[SignedDte, ...],
        *,
        issuer_rut: str,
        sender_rut: str,
        authorization: EnvelopeAuthorization,
        signed_at: datetime,
        credential: SigningCredential,
        set_id: str = "SetDoc",
        receiver_rut: str = SII_RUT,
    ) -> SignedEnvelope:
        if not 1 <= len(documents) <= 500:
            raise ValueError("EnvioDTE debe contener entre 1 y 500 documentos")
        issuer_rut = normalize_rut(issuer_rut)
        sender_rut = normalize_rut(sender_rut)
        receiver_rut = normalize_rut(receiver_rut)
        if not set_id or not set_id[0].isalpha() or not set_id.replace("_", "").isalnum():
            raise ValueError("set_id debe ser un ID XML simple")

        signer = XmlSigner()
        identities = []
        for document in documents:
            if not signer.verify_with_certificate(document, credential.certificate):
                raise ValueError(
                    "EnvioDTE contiene un documento cuya firma no corresponde a la credencial"
                )
            document_issuer, document_type, folio = _document_identity(document)
            if document_issuer != issuer_rut:
                raise ValueError("EnvioDTE contiene un documento de otro emisor")
            if document_type not in {33, 34, 52, 56, 61}:
                raise ValueError("EnvioDTE contiene un tipo documental no habilitado")
            if receiver_rut != self.SII_RUT and _document_receiver(document) != receiver_rut:
                raise ValueError("El intercambio contiene una factura para otro receptor")
            identities.append((document.document_id, document_type, folio))
        if len(identities) != len(set(identities)):
            raise ValueError("EnvioDTE no puede repetir un mismo documento")
        folios = [(document_type, folio) for _, document_type, folio in identities]
        if len(folios) != len(set(folios)):
            raise ValueError("EnvioDTE no puede repetir tipo y folio")

        counts = Counter(document_type for _, document_type, _ in identities)
        subtotals = b"".join(
            b"<SubTotDTE>"
            + _element("TpoDTE", str(document_type))
            + _element("NroDTE", str(count))
            + b"</SubTotDTE>"
            for document_type, count in sorted(counts.items())
        )
        caratula = (
            b'<Caratula version="1.0">'
            + _element("RutEmisor", issuer_rut)
            + _element("RutEnvia", sender_rut)
            + _element("RutReceptor", receiver_rut)
            + _element("FchResol", authorization.resolution_date.isoformat())
            + _element("NroResol", str(authorization.resolution_number))
            + _element("TmstFirmaEnv", _sii_local_timestamp(signed_at))
            + subtotals
            + b"</Caratula>"
        )
        embedded = b"".join(_without_declaration(document.xml) for document in documents)
        unsigned = (
            b'<?xml version="1.0" encoding="ISO-8859-1"?>'
            b'<EnvioDTE version="1.0" xmlns="http://www.sii.cl/SiiDte">'
            b'<SetDTE ID="'
            + set_id.encode("ascii")
            + b'">'
            + caratula
            + embedded
            + b"</SetDTE></EnvioDTE>"
        )
        signed = signer.sign_raw(
            unsigned,
            target_tag=f"{{{SII}}}SetDTE",
            target_id=set_id,
            credential=credential,
        )
        return SignedEnvelope(xml=signed, set_id=set_id)


def _without_declaration(xml: bytes) -> bytes:
    marker = b"?>"
    if xml.startswith(b"<?xml"):
        return xml[xml.index(marker) + len(marker):]
    return xml


def _document_identity(document: SignedDte) -> tuple[str, int, int]:
    try:
        root = etree.fromstring(
            document.xml,
            etree.XMLParser(resolve_entities=False, no_network=True),
        )
        nodes = root.xpath("//*[local-name()='Documento']")
        if len(nodes) != 1 or nodes[0].get("ID") != document.document_id:
            raise ValueError("El DTE no contiene el Documento esperado")
        issuer = normalize_rut(_required_local_text(nodes[0], "RUTEmisor"))
        document_type = int(_required_local_text(nodes[0], "TipoDTE"))
        folio = int(_required_local_text(nodes[0], "Folio"))
    except (etree.XMLSyntaxError, TypeError, ValueError) as exc:
        raise ValueError("EnvioBOLETA contiene un DTE inválido") from exc
    return issuer, document_type, folio


def _document_receiver(document: SignedDte) -> str:
    try:
        root = etree.fromstring(
            document.xml,
            etree.XMLParser(resolve_entities=False, no_network=True),
        )
        nodes = root.xpath("//*[local-name()='Documento']")
        if len(nodes) != 1:
            raise ValueError("El DTE no contiene un Documento único")
        return normalize_rut(_required_local_text(nodes[0], "RUTRecep"))
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise ValueError("EnvioDTE contiene un receptor inválido") from exc


def _required_local_text(root: etree._Element, name: str) -> str:
    values = root.xpath(f".//*[local-name()='{name}']/text()")
    if len(values) != 1 or not str(values[0]).strip():
        raise ValueError(f"El DTE no contiene un único {name}")
    return str(values[0]).strip()
