"""Construcción de documentos DTE 39/41 previos a XMLDSig."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import re

from .boleta import BoletaAfecta, BoletaExenta
from .ted import SignedTed, TedError, _element, _sii_local_timestamp


@dataclass(frozen=True)
class UnsignedDte:
    xml: bytes
    document_id: str


class DteBuilder:
    def build(
        self,
        boleta: BoletaAfecta | BoletaExenta,
        ted: SignedTed,
        *,
        signed_at: datetime,
    ) -> UnsignedDte:
        self._assert_ted_matches(boleta, ted)
        document_id = f"F{boleta.folio}T{boleta.document_type}"
        issuer = boleta.issuer

        id_doc = (
            _element("TipoDTE", str(boleta.document_type))
            + _element("Folio", str(boleta.folio))
            + _element("FchEmis", boleta.issued_on.isoformat())
            + _element("IndServicio", str(boleta.service_indicator))
        )
        emitter = (
            _element("RUTEmisor", issuer.rut)
            + _element("RznSocEmisor", issuer.legal_name)
            + _element("GiroEmisor", issuer.business_activity)
        )
        if issuer.address is not None:
            emitter += _element("DirOrigen", issuer.address)
        if issuer.commune is not None:
            emitter += _element("CmnaOrigen", issuer.commune)

        receiver = _element("RUTRecep", boleta.receiver_rut) + _element(
            "RznSocRecep",
            boleta.receiver_name,
        )
        header = (
            b"<Encabezado><IdDoc>"
            + id_doc
            + b"</IdDoc><Emisor>"
            + emitter
            + b"</Emisor><Receptor>"
            + receiver
            + b"</Receptor><Totales>"
            + (
                _element("MntNeto", str(boleta.net_total))
                if boleta.document_type == 39
                else b""
            )
            + (
                _element("MntExe", str(boleta.exempt_total))
                if boleta.exempt_total
                else b""
            )
            + (
                _element("IVA", str(boleta.vat_total))
                if boleta.document_type == 39
                else b""
            )
            + _element("MntTotal", str(boleta.total))
            + b"</Totales></Encabezado>"
        )
        details = b"".join(
            self._detail(index, line) for index, line in enumerate(boleta.lines, 1)
        )
        reference = b""
        if boleta.reference_code is not None:
            reference = (
                b"<Referencia>"
                + _element("NroLinRef", "1")
                + _element("CodRef", boleta.reference_code)
                + _element("RazonRef", boleta.reference_reason)
                + b"</Referencia>"
            )
        document = (
            b'<Documento ID="'
            + document_id.encode("ascii")
            + b'">'
            + header
            + details
            + reference
            + ted.xml
            + _element("TmstFirma", _sii_local_timestamp(signed_at))
            + b"</Documento>"
        )
        xml = (
            b'<?xml version="1.0" encoding="ISO-8859-1"?>'
            b'<DTE version="1.0" xmlns="http://www.sii.cl/SiiDte">'
            + document
            + b"</DTE>"
        )
        return UnsignedDte(xml=xml, document_id=document_id)

    @staticmethod
    def _detail(index: int, line) -> bytes:
        content = _element("NroLinDet", str(index))
        if line.is_exempt:
            content += _element("IndExe", "1")
        content += _element("NmbItem", line.name)
        content += _element("QtyItem", _decimal_text(line.quantity))
        if line.unit_measure is not None:
            content += _element("UnmdItem", line.unit_measure)
        content += _element("PrcItem", _decimal_text(line.unit_price_gross))
        if line.discount_gross:
            content += _element("DescuentoMonto", _decimal_text(line.discount_gross))
        content += _element("MontoItem", str(line.gross_total))
        return b"<Detalle>" + content + b"</Detalle>"

    @staticmethod
    def _assert_ted_matches(
        boleta: BoletaAfecta | BoletaExenta,
        ted: SignedTed,
    ) -> None:
        expected = {
            b"RE": boleta.issuer_rut,
            b"TD": str(boleta.document_type),
            b"F": str(boleta.folio),
            b"FE": boleta.issued_on.isoformat(),
            b"MNT": str(boleta.total),
        }
        for tag, value in expected.items():
            pattern = (
                rb"<"
                + tag
                + rb">"
                + re.escape(value.encode("ascii"))
                + rb"</"
                + tag
                + rb">"
            )
            if re.search(pattern, ted.dd) is None:
                raise TedError(f"El TED no coincide con el DTE en {tag.decode()}")


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
