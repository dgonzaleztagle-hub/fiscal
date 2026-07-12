"""Construcción de guía de despacho DTE 52 antes de XMLDSig."""

from datetime import datetime
import re

from .dispatch import DispatchDocument, DispatchError
from .dte import UnsignedDte, _decimal_text
from .fiscal_document import TaxCategory
from .ted import SignedTed, TedError, _element, _sii_local_timestamp


class DispatchDteBuilder:
    def build(
        self,
        guide: DispatchDocument,
        ted: SignedTed,
        *,
        signed_at: datetime,
    ) -> UnsignedDte:
        if guide.transport.has_future_fields:
            raise DispatchError(
                "El XSD oficial vigente aún no admite patente de carro ni fechas de traslado"
            )
        self._assert_ted_matches(guide, ted)
        document_id = f"F{guide.folio}T52"
        id_doc = (
            _element("TipoDTE", "52")
            + _element("Folio", str(guide.folio))
            + _element("FchEmis", guide.issued_on.isoformat())
        )
        if guide.dispatch_account is not None:
            id_doc += _element("TipoDespacho", str(int(guide.dispatch_account)))
        id_doc += _element("IndTraslado", str(int(guide.reason)))

        issuer = guide.issuer
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

        party = guide.receiver
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

        transport = self._transport(guide)
        totals = _element("MntNeto", str(guide.net_total))
        if guide.exempt_total:
            totals += _element("MntExe", str(guide.exempt_total))
        totals += (
            _element("TasaIVA", "19")
            + _element("IVA", str(guide.vat_total))
            + _element("MntTotal", str(guide.total))
        )
        header = (
            b"<Encabezado><IdDoc>"
            + id_doc
            + b"</IdDoc><Emisor>"
            + emitter
            + b"</Emisor><Receptor>"
            + receiver
            + b"</Receptor>"
            + transport
            + b"<Totales>"
            + totals
            + b"</Totales></Encabezado>"
        )
        details = b"".join(
            self._detail(guide, index, line)
            for index, line in enumerate(guide.lines, 1)
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
    def _transport(guide: DispatchDocument) -> bytes:
        value = guide.transport
        content = b""
        if value.vehicle_plate is not None:
            content += _element("Patente", value.vehicle_plate)
        if value.carrier_rut is not None:
            content += _element("RUTTrans", value.carrier_rut)
        if value.driver_rut is not None:
            content += (
                b"<Chofer>"
                + _element("RUTChofer", value.driver_rut)
                + _element("NombreChofer", value.driver_name)
                + b"</Chofer>"
            )
        if value.destination_address is not None:
            content += _element("DirDest", value.destination_address)
        if value.destination_commune is not None:
            content += _element("CmnaDest", value.destination_commune)
        if value.destination_city is not None:
            content += _element("CiudadDest", value.destination_city)
        return b"<Transporte>" + content + b"</Transporte>" if content else b""

    @staticmethod
    def _detail(guide: DispatchDocument, index: int, line) -> bytes:
        content = _element("NroLinDet", str(index))
        if guide.is_valued and line.tax_category is TaxCategory.EXEMPT:
            content += _element("IndExe", "1")
        content += _element("NmbItem", line.name)
        if line.description is not None:
            content += _element("DscItem", line.description)
        content += _element("QtyItem", _decimal_text(line.quantity))
        if line.unit_measure is not None:
            content += _element("UnmdItem", line.unit_measure)
        if guide.is_valued:
            content += _element("PrcItem", _decimal_text(line.unit_price))
        content += _element("MontoItem", str(guide.line_amount(line)))
        return b"<Detalle>" + content + b"</Detalle>"

    @staticmethod
    def _assert_ted_matches(guide: DispatchDocument, ted: SignedTed) -> None:
        expected = {
            b"RE": guide.issuer_rut,
            b"TD": "52",
            b"F": str(guide.folio),
            b"FE": guide.issued_on.isoformat(),
            b"MNT": str(guide.total),
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
                raise TedError(f"El TED no coincide con la guía en {tag.decode()}")
