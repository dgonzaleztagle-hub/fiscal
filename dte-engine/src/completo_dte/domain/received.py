"""Validación de seguridad y extracción mínima de DTE recibidos."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path

from lxml import etree

from .fiscal_document import DocumentType
from .rut import normalize_rut
from .schema import XmlSchemaValidator
from .xml_signature import SignedDte, XmlSigner


class ReceivedDocumentError(ValueError):
    """El XML recibido no es un DTE confiable para registrar."""


@dataclass(frozen=True)
class ReceivedLine:
    line_number: int
    name: str
    quantity: Decimal | None
    amount: int


@dataclass(frozen=True)
class ReceivedDocument:
    document_id: str
    document_type: DocumentType
    folio: int
    issued_on: date
    issuer_rut: str
    issuer_name: str
    receiver_rut: str
    total: int
    lines: tuple[ReceivedLine, ...]
    xml_sha256: str
    signed_xml: bytes


class ReceivedDocumentValidator:
    def __init__(self, official_dte_schema: str | Path) -> None:
        self._schema = XmlSchemaValidator(official_dte_schema)

    def validate(self, xml: bytes, *, expected_receiver_rut: str) -> ReceivedDocument:
        if len(xml) > 5_000_000:
            raise ReceivedDocumentError("El XML recibido excede 5 MB")
        parser = etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            load_dtd=False,
            huge_tree=False,
            remove_blank_text=False,
        )
        try:
            root = etree.fromstring(xml, parser)
        except etree.XMLSyntaxError as exc:
            raise ReceivedDocumentError("El archivo no contiene XML válido") from exc
        if etree.QName(root).localname != "DTE":
            raise ReceivedDocumentError("Se esperaba un DTE individual")
        documents = root.xpath("/*[local-name()='DTE']/*[local-name()='Documento']")
        if len(documents) != 1:
            raise ReceivedDocumentError("El DTE debe contener un único Documento")
        document_id = documents[0].get("ID")
        if not document_id:
            raise ReceivedDocumentError("El Documento no contiene ID")
        try:
            self._schema.validate(xml)
        except ValueError as exc:
            raise ReceivedDocumentError("El DTE no cumple el XSD oficial fijado") from exc
        signed = SignedDte(xml=xml, document_id=document_id)
        if not XmlSigner().verify(signed):
            raise ReceivedDocumentError("La firma XMLDSig del emisor no es válida")

        def required(tag: str) -> str:
            values = root.xpath("//*[local-name()=$tag]/text()", tag=tag)
            if len(values) != 1 or not str(values[0]).strip():
                raise ReceivedDocumentError(f"El DTE no contiene {tag} único")
            return str(values[0]).strip()

        try:
            document_type = DocumentType(int(required("TipoDTE")))
            folio = int(required("Folio"))
            issued_on = date.fromisoformat(required("FchEmis"))
            total = int(required("MntTotal"))
            issuer_rut = normalize_rut(required("RUTEmisor"))
            receiver_rut = normalize_rut(required("RUTRecep"))
        except (ValueError, TypeError) as exc:
            raise ReceivedDocumentError("El encabezado tributario recibido es inválido") from exc
        if receiver_rut != normalize_rut(expected_receiver_rut):
            raise ReceivedDocumentError("El DTE fue emitido para otro contribuyente")
        lines = tuple(_received_line(node) for node in root.xpath("//*[local-name()='Detalle']"))
        if not lines or len({line.line_number for line in lines}) != len(lines):
            raise ReceivedDocumentError("El detalle recibido está vacío o repite líneas")
        return ReceivedDocument(
            document_id=document_id,
            document_type=document_type,
            folio=folio,
            issued_on=issued_on,
            issuer_rut=issuer_rut,
            issuer_name=required("RznSoc"),
            receiver_rut=receiver_rut,
            total=total,
            lines=lines,
            xml_sha256=hashlib.sha256(xml).hexdigest(),
            signed_xml=xml,
        )


def _received_line(node) -> ReceivedLine:
    def one(name: str, *, required: bool = True) -> str | None:
        values = node.xpath("./*[local-name()=$name]/text()", name=name)
        if len(values) > 1 or (required and len(values) != 1):
            raise ReceivedDocumentError(f"Detalle con {name} inválido")
        return str(values[0]).strip() if values else None

    try:
        quantity_text = one("QtyItem", required=False)
        return ReceivedLine(
            line_number=int(one("NroLinDet")),
            name=str(one("NmbItem")),
            quantity=Decimal(quantity_text) if quantity_text is not None else None,
            amount=int(one("MontoItem")),
        )
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise ReceivedDocumentError("Detalle tributario recibido inválido") from exc
