"""Construcción de facturas DTE 33/34 antes de XMLDSig."""

from datetime import datetime
import re

from .dte import UnsignedDte, _decimal_text
from .fiscal_document import DocumentType, TaxCategory
from .invoice import Invoice
from .ted import SignedTed, TedError, _element, _sii_local_timestamp


class InvoiceDteBuilder:
    def build(
        self,
        invoice: Invoice,
        ted: SignedTed,
        *,
        signed_at: datetime,
    ) -> UnsignedDte:
        self._assert_ted_matches(invoice, ted)
        document_id = f"F{invoice.folio}T{int(invoice.document_type)}"
        id_doc = (
            _element("TipoDTE", str(int(invoice.document_type)))
            + _element("Folio", str(invoice.folio))
            + _element("FchEmis", invoice.issued_on.isoformat())
            + _element("FmaPago", str(int(invoice.payment_terms)))
        )
        if invoice.due_on is not None:
            id_doc += _element("FchVenc", invoice.due_on.isoformat())

        issuer = invoice.issuer
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

        party = invoice.receiver
        receiver = (
            _element("RUTRecep", party.rut)
            + _element("RznSocRecep", party.legal_name)
            + _element("GiroRecep", party.business_activity)
        )
        if party.phone is not None:
            receiver += _element("Contacto", party.phone)
        if party.email is not None:
            receiver += _element("CorreoRecep", party.email)
        receiver += _element("DirRecep", party.address) + _element(
            "CmnaRecep", party.commune
        )
        if party.city is not None:
            receiver += _element("CiudadRecep", party.city)

        totals = b""
        if invoice.document_type == DocumentType.FACTURA_AFECTA:
            totals += _element("MntNeto", str(invoice.net_total))
            if invoice.exempt_total:
                totals += _element("MntExe", str(invoice.exempt_total))
            totals += _element("TasaIVA", "19") + _element(
                "IVA", str(invoice.vat_total)
            )
        else:
            totals += _element("MntExe", str(invoice.exempt_total))
        totals += _element("MntTotal", str(invoice.total))

        header = (
            b"<Encabezado><IdDoc>"
            + id_doc
            + b"</IdDoc><Emisor>"
            + emitter
            + b"</Emisor><Receptor>"
            + receiver
            + b"</Receptor><Totales>"
            + totals
            + b"</Totales></Encabezado>"
        )
        details = b"".join(
            self._detail(invoice, index, line)
            for index, line in enumerate(invoice.lines, 1)
        )
        document = (
            b'<Documento ID="'
            + document_id.encode("ascii")
            + b'">'
            + header
            + details
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
    def _detail(invoice: Invoice, index: int, line) -> bytes:
        amounts = invoice.line_amounts(line)
        content = _element("NroLinDet", str(index))
        if (
            invoice.document_type == DocumentType.FACTURA_AFECTA
            and line.tax_category == TaxCategory.EXEMPT
        ):
            content += _element("IndExe", "1")
        content += _element("NmbItem", line.name)
        if line.description is not None:
            content += _element("DscItem", line.description)
        content += _element("QtyItem", _decimal_text(line.quantity))
        if line.unit_measure is not None:
            content += _element("UnmdItem", line.unit_measure)
        content += _element("PrcItem", _decimal_text(line.unit_price))
        if line.discount_percent:
            content += _element("DescuentoPct", _decimal_text(line.discount_percent))
        if amounts.discount:
            content += _element("DescuentoMonto", str(amounts.discount))
        if line.surcharge_percent:
            content += _element("RecargoPct", _decimal_text(line.surcharge_percent))
        if amounts.surcharge:
            content += _element("RecargoMonto", str(amounts.surcharge))
        content += _element("MontoItem", str(amounts.amount))
        return b"<Detalle>" + content + b"</Detalle>"

    @staticmethod
    def _assert_ted_matches(invoice: Invoice, ted: SignedTed) -> None:
        expected = {
            b"RE": invoice.issuer_rut,
            b"TD": str(int(invoice.document_type)),
            b"F": str(invoice.folio),
            b"FE": invoice.issued_on.isoformat(),
            b"MNT": str(invoice.total),
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
                raise TedError(f"El TED no coincide con la factura en {tag.decode()}")
