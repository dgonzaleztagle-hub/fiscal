"""Construcción de notas 56/61 de corrección de montos."""

from datetime import datetime
import re

from .correction import CorrectionDocument
from .dte import UnsignedDte, _decimal_text
from .fiscal_document import CorrectionCode, TaxCategory
from .ted import SignedTed, TedError, _element, _sii_local_timestamp


class CorrectionDteBuilder:
    def build(
        self,
        correction: CorrectionDocument,
        ted: SignedTed,
        *,
        signed_at: datetime,
    ) -> UnsignedDte:
        self._assert_ted_matches(correction, ted)
        document_id = f"F{correction.folio}T{int(correction.document_type)}"
        issuer = correction.issuer
        receiver = correction.receiver
        id_doc = (
            _element("TipoDTE", str(int(correction.document_type)))
            + _element("Folio", str(correction.folio))
            + _element("FchEmis", correction.issued_on.isoformat())
        )
        emitter = (
            _element("RUTEmisor", issuer.rut)
            + _element("RznSoc", issuer.legal_name)
            + _element("GiroEmis", issuer.business_activity)
            + _element("Acteco", str(issuer.activity_code))
        )
        if issuer.address is not None:
            emitter += _element("DirOrigen", issuer.address)
        if issuer.commune is not None:
            emitter += _element("CmnaOrigen", issuer.commune)
        recipient = (
            _element("RUTRecep", receiver.rut)
            + _element("RznSocRecep", receiver.legal_name)
            + _element("GiroRecep", receiver.business_activity)
        )
        if receiver.email is not None:
            recipient += _element("CorreoRecep", receiver.email)
        recipient += _element("DirRecep", receiver.address) + _element(
            "CmnaRecep", receiver.commune
        )
        totals = b""
        if correction.reference.code is CorrectionCode.FIX_TEXT:
            totals += _element("MntNeto", "0") + _element("MntExe", "0")
        elif correction.net_total:
            totals += _element("MntNeto", str(correction.net_total))
        if correction.exempt_total:
            totals += _element("MntExe", str(correction.exempt_total))
        if correction.net_total:
            totals += _element("TasaIVA", "19") + _element(
                "IVA", str(correction.vat_total)
            )
        totals += _element("MntTotal", str(correction.total))
        header = (
            b"<Encabezado><IdDoc>"
            + id_doc
            + b"</IdDoc><Emisor>"
            + emitter
            + b"</Emisor><Receptor>"
            + recipient
            + b"</Receptor><Totales>"
            + totals
            + b"</Totales></Encabezado>"
        )
        details = b"".join(
            self._detail(correction, index, line)
            for index, line in enumerate(correction.lines, 1)
        )
        reference = correction.reference
        reference_xml = (
            b"<Referencia>"
            + _element("NroLinRef", "1")
            + _element("TpoDocRef", str(int(reference.document_type)))
            + _element("FolioRef", str(reference.folio))
            + _element("FchRef", reference.issued_on.isoformat())
            + _element("CodRef", str(int(reference.code)))
            + _element("RazonRef", reference.reason)
            + b"</Referencia>"
        )
        document = (
            b'<Documento ID="'
            + document_id.encode("ascii")
            + b'">'
            + header
            + details
            + reference_xml
            + ted.xml
            + _element("TmstFirma", _sii_local_timestamp(signed_at))
            + b"</Documento>"
        )
        return UnsignedDte(
            xml=(
                b'<?xml version="1.0" encoding="ISO-8859-1"?>'
                b'<DTE version="1.0" xmlns="http://www.sii.cl/SiiDte">'
                + document
                + b"</DTE>"
            ),
            document_id=document_id,
        )

    @staticmethod
    def _detail(correction, index, line) -> bytes:
        amounts = correction.line_amounts(line)
        content = _element("NroLinDet", str(index))
        if line.tax_category == TaxCategory.EXEMPT:
            content += _element("IndExe", "1")
        content += _element("NmbItem", line.name)
        if correction.reference.code is not CorrectionCode.FIX_TEXT:
            content += _element("QtyItem", _decimal_text(line.quantity))
            content += _element("PrcItem", _decimal_text(line.unit_price))
        content += _element("MontoItem", str(amounts.amount))
        return b"<Detalle>" + content + b"</Detalle>"

    @staticmethod
    def _assert_ted_matches(correction, ted: SignedTed) -> None:
        expected = {
            b"RE": correction.issuer_rut,
            b"TD": str(int(correction.document_type)),
            b"F": str(correction.folio),
            b"FE": correction.issued_on.isoformat(),
            b"MNT": str(correction.total),
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
                raise TedError(f"El TED no coincide con la nota en {tag.decode()}")
