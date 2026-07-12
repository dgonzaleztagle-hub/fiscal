"""Representación PDF térmica de una boleta electrónica."""

from dataclasses import dataclass
from io import BytesIO
import re
from urllib.parse import urlparse

from lxml import etree
from pdf417gen import encode, render_image
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas


class ReceiptError(ValueError):
    """El XML o la configuración no permiten producir una boleta confiable."""


@dataclass(frozen=True)
class ReceiptConfig:
    verification_url: str
    resolution_number: int
    resolution_year: int
    paper_width_mm: int = 80

    def __post_init__(self) -> None:
        parsed = urlparse(self.verification_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ReceiptError("La URL de consulta debe ser HTTPS")
        if self.paper_width_mm < 57:
            raise ReceiptError("El papel no puede tener menos de 57 mm de ancho")
        if self.resolution_number < 0 or not 2000 <= self.resolution_year <= 2100:
            raise ReceiptError("Resolución SII inválida")


class BoletaReceiptRenderer:
    """Renderiza desde el DTE; nunca recalcula el documento desde la venta."""

    def render(self, signed_xml: bytes, config: ReceiptConfig) -> bytes:
        root = _parse(signed_xml)
        document_type = _required(root, "TipoDTE")
        if document_type not in {"39", "41"}:
            raise ReceiptError("Sólo se pueden representar boletas tipo 39 o 41")

        details = root.xpath("//*[local-name()='Detalle']")
        ted_nodes = root.xpath("//*[local-name()='TED']")
        if not details or len(ted_nodes) != 1:
            raise ReceiptError("El DTE debe contener detalle y un único TED")
        ted = _extract_original_ted(signed_xml)
        barcode = _pdf417(ted)

        height = max(150, 112 + len(details) * 9) * mm
        width = config.paper_width_mm * mm
        output = BytesIO()
        canvas = Canvas(output, pagesize=(width, height), pageCompression=1)
        y = height - 7 * mm

        def centered(
            text: str, size: float, *, bold: bool = False, gap: float = 4.2
        ) -> None:
            nonlocal y
            canvas.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            canvas.drawCentredString(width / 2, y, text)
            y -= gap * mm

        def pair(label: str, value: str, *, bold: bool = False) -> None:
            nonlocal y
            canvas.setFont("Helvetica-Bold" if bold else "Helvetica", 8)
            canvas.drawString(5 * mm, y, label)
            canvas.drawRightString(width - 5 * mm, y, value)
            y -= 4 * mm

        centered(_required(root, "RznSocEmisor"), 10, bold=True, gap=5)
        centered(f"RUT: {_required(root, 'RUTEmisor')}", 8)
        centered(_required(root, "GiroEmisor"), 7)
        address = " - ".join(
            value
            for value in (_optional(root, "DirOrigen"), _optional(root, "CmnaOrigen"))
            if value
        )
        if address:
            centered(address, 7, gap=5)

        canvas.line(5 * mm, y, width - 5 * mm, y)
        y -= 5 * mm
        title = (
            "BOLETA ELECTRÓNICA"
            if document_type == "39"
            else "BOLETA EXENTA ELECTRÓNICA"
        )
        centered(title, 10, bold=True)
        centered(f"N° {_required(root, 'Folio')}", 11, bold=True, gap=5)
        pair("Fecha", _required(root, "FchEmis"))
        y -= 1 * mm
        canvas.line(5 * mm, y, width - 5 * mm, y)
        y -= 5 * mm

        for detail in details:
            name = _child_required(detail, "NmbItem")
            quantity = _child_required(detail, "QtyItem")
            unit = _child_optional(detail, "UnmdItem")
            amount = _child_required(detail, "MontoItem")
            canvas.setFont("Helvetica", 7.5)
            canvas.drawString(5 * mm, y, _fit(name, 38))
            canvas.drawRightString(
                width - 5 * mm,
                y,
                f"{quantity}{' ' + unit if unit else ''}  ${_clp(amount)}",
            )
            y -= 4 * mm

        y -= 1 * mm
        canvas.line(5 * mm, y, width - 5 * mm, y)
        y -= 5 * mm
        if _optional(root, "MntNeto"):
            pair("Neto", f"${_clp(_required(root, 'MntNeto'))}")
        if _optional(root, "MntExe"):
            pair("Exento", f"${_clp(_required(root, 'MntExe'))}")
        if _optional(root, "IVA"):
            pair("IVA", f"${_clp(_required(root, 'IVA'))}")
        pair("TOTAL", f"${_clp(_required(root, 'MntTotal'))}", bold=True)
        y -= 2 * mm

        image_width_px, image_height_px = barcode.size
        stamp_width = 50 * mm
        stamp_height = stamp_width * image_height_px / image_width_px
        if stamp_height < 20 * mm:
            scale = (20 * mm) / stamp_height
            stamp_width *= scale
            stamp_height *= scale
        if stamp_width > width - 10 * mm:
            scale = (width - 10 * mm) / stamp_width
            stamp_width *= scale
            stamp_height *= scale
        canvas.drawImage(
            ImageReader(barcode),
            (width - stamp_width) / 2,
            y - stamp_height,
            stamp_width,
            stamp_height,
            preserveAspectRatio=True,
            mask="auto",
        )
        y -= stamp_height + 4 * mm
        centered("Timbre electrónico SII", 7, bold=True)
        centered(
            f"Res. {config.resolution_number} de {config.resolution_year}",
            7,
        )
        centered(f"Verifique documento: {config.verification_url}", 6.5)
        canvas.showPage()
        canvas.save()
        return output.getvalue()


def _parse(payload: bytes) -> etree._Element:
    try:
        return etree.fromstring(
            payload,
            etree.XMLParser(
                resolve_entities=False, no_network=True, remove_blank_text=False
            ),
        )
    except etree.XMLSyntaxError as exc:
        raise ReceiptError("El DTE no es XML válido") from exc


def _required(root: etree._Element, name: str) -> str:
    values = root.xpath(f"//*[local-name()='{name}']/text()")
    if not values or not str(values[0]).strip():
        raise ReceiptError(f"El DTE no contiene {name}")
    return str(values[0]).strip()


def _optional(root: etree._Element, name: str) -> str | None:
    values = root.xpath(f"//*[local-name()='{name}']/text()")
    return str(values[0]).strip() if values and str(values[0]).strip() else None


def _child_required(root: etree._Element, name: str) -> str:
    value = _child_optional(root, name)
    if value is None:
        raise ReceiptError(f"El detalle no contiene {name}")
    return value


def _child_optional(root: etree._Element, name: str) -> str | None:
    values = root.xpath(f"./*[local-name()='{name}']/text()")
    return str(values[0]).strip() if values and str(values[0]).strip() else None


def _pdf417(ted: bytes):
    try:
        # 18 columnas mantiene un aspecto cercano a 4,5 x 2 cm para un TED
        # típico, evitando el timbre alto y angosto de impresoras térmicas.
        codes = encode(ted, columns=18, security_level=5)
        return render_image(codes, scale=4, ratio=3, padding=8)
    except (ValueError, UnicodeError) as exc:
        raise ReceiptError("No fue posible codificar el TED en PDF417") from exc


def _extract_original_ted(payload: bytes) -> bytes:
    match = re.search(rb"<TED\b.*?</TED>", payload, flags=re.DOTALL)
    if match is None:
        raise ReceiptError("No fue posible preservar el TED original")
    return match.group(0)


def _clp(value: str) -> str:
    return f"{int(value):,}".replace(",", ".")


def _fit(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"
