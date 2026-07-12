"""Construcción y firma del Resumen de Ventas Diarias (RCOF/RVD)."""

from dataclasses import dataclass
from datetime import date, datetime

from .certificate import SigningCredential
from .envelope import EnvelopeAuthorization
from .rut import normalize_rut
from .ted import _element, _sii_local_timestamp
from .xml_signature import SII, XmlSigner


class DailySummaryError(ValueError):
    """El consumo diario de folios no es consistente."""


@dataclass(frozen=True)
class DailyFolio:
    document_type: int
    folio: int
    issued_on: date
    net_amount: int = 0
    vat_amount: int = 0
    exempt_amount: int = 0
    total_amount: int = 0
    voided: bool = False

    def __post_init__(self) -> None:
        if self.document_type not in (39, 41, 61):
            raise DailySummaryError("El RCOF sólo admite documentos 39, 41 y 61")
        if not 1 <= self.folio <= 9_999_999_999:
            raise DailySummaryError("El folio del RCOF está fuera de rango")
        amounts = (
            self.net_amount,
            self.vat_amount,
            self.exempt_amount,
            self.total_amount,
        )
        if any(amount < 0 for amount in amounts):
            raise DailySummaryError("Los montos del RCOF no pueden ser negativos")
        if self.voided and any(amounts):
            raise DailySummaryError("Un folio anulado no puede informar montos")
        if not self.voided:
            if self.total_amount <= 0:
                raise DailySummaryError(
                    "Un folio emitido debe tener monto total positivo"
                )
            if (
                self.net_amount + self.vat_amount + self.exempt_amount
                != self.total_amount
            ):
                raise DailySummaryError("Neto, IVA y exento no cuadran con el total")


@dataclass(frozen=True)
class SignedDailySummary:
    xml: bytes
    document_id: str


class DailySummaryBuilder:
    def build(
        self,
        folios: tuple[DailyFolio, ...],
        *,
        issuer_rut: str,
        sender_rut: str,
        authorization: EnvelopeAuthorization,
        sequence: int,
        signed_at: datetime,
        credential: SigningCredential,
        document_id: str = "RCOF",
    ) -> SignedDailySummary:
        if not folios:
            raise DailySummaryError("El RCOF necesita al menos un folio utilizado")
        if not 1 <= sequence <= 999:
            raise DailySummaryError("La secuencia del RCOF debe estar entre 1 y 999")
        if (
            not document_id
            or not document_id[0].isalpha()
            or not document_id.replace("_", "").isalnum()
        ):
            raise DailySummaryError("document_id debe ser un ID XML simple")
        issuer_rut = normalize_rut(issuer_rut)
        sender_rut = normalize_rut(sender_rut)
        keys = [(folio.document_type, folio.folio) for folio in folios]
        if len(keys) != len(set(keys)):
            raise DailySummaryError("Un folio no puede repetirse en el RCOF")

        dates = tuple(folio.issued_on for folio in folios)
        if len(set(dates)) != 1:
            raise DailySummaryError(
                "El RCOF diario sólo puede contener folios de una misma fecha"
            )
        caratula = (
            b'<Caratula version="1.0">'
            + _element("RutEmisor", issuer_rut)
            + _element("RutEnvia", sender_rut)
            + _element("FchResol", authorization.resolution_date.isoformat())
            + _element("NroResol", str(authorization.resolution_number))
            + _element("FchInicio", min(dates).isoformat())
            + _element("FchFinal", max(dates).isoformat())
            + _element("SecEnvio", str(sequence))
            + _element("TmstFirmaEnv", _sii_local_timestamp(signed_at))
            + b"</Caratula>"
        )
        summaries = b"".join(
            self._summary(document_type, folios)
            for document_type in sorted({folio.document_type for folio in folios})
        )
        unsigned = (
            b'<?xml version="1.0" encoding="ISO-8859-1"?>'
            b'<ConsumoFolios version="1.0" xmlns="http://www.sii.cl/SiiDte">'
            b'<DocumentoConsumoFolios ID="'
            + document_id.encode("ascii")
            + b'">'
            + caratula
            + summaries
            + b"</DocumentoConsumoFolios></ConsumoFolios>"
        )
        signed = XmlSigner().sign_raw(
            unsigned,
            target_tag=f"{{{SII}}}DocumentoConsumoFolios",
            target_id=document_id,
            credential=credential,
        )
        return SignedDailySummary(xml=signed, document_id=document_id)

    @staticmethod
    def _summary(document_type: int, all_folios: tuple[DailyFolio, ...]) -> bytes:
        folios = tuple(
            sorted(
                (folio for folio in all_folios if folio.document_type == document_type),
                key=lambda folio: folio.folio,
            )
        )
        emitted = tuple(folio for folio in folios if not folio.voided)
        voided = tuple(folio for folio in folios if folio.voided)
        net = sum(folio.net_amount for folio in emitted)
        vat = sum(folio.vat_amount for folio in emitted)
        exempt = sum(folio.exempt_amount for folio in emitted)
        total = sum(folio.total_amount for folio in emitted)

        content = _element("TipoDocumento", str(document_type))
        if net:
            content += _element("MntNeto", str(net))
        if vat:
            content += _element("MntIva", str(vat)) + _element("TasaIVA", "19")
        if exempt:
            content += _element("MntExento", str(exempt))
        content += (
            _element("MntTotal", str(total))
            + _element("FoliosEmitidos", str(len(emitted)))
            + _element("FoliosAnulados", str(len(voided)))
            + _element("FoliosUtilizados", str(len(folios)))
        )
        for start, end in _continuous_ranges(tuple(folio.folio for folio in folios)):
            content += (
                b"<RangoUtilizados>"
                + _element("Inicial", str(start))
                + _element("Final", str(end))
                + b"</RangoUtilizados>"
            )
        for start, end in _continuous_ranges(tuple(folio.folio for folio in voided)):
            content += (
                b"<RangoAnulados>"
                + _element("Inicial", str(start))
                + _element("Final", str(end))
                + b"</RangoAnulados>"
            )
        return b"<Resumen>" + content + b"</Resumen>"


def _continuous_ranges(folios: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    if not folios:
        return ()
    ordered = sorted(set(folios))
    ranges: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for folio in ordered[1:]:
        if folio != previous + 1:
            ranges.append((start, previous))
            start = folio
        previous = folio
    ranges.append((start, previous))
    return tuple(ranges)
