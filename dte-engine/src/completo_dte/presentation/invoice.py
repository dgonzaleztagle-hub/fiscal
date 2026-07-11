"""Representación PDF carta derivada de un DTE nominativo inmutable."""

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from .receipt import (
    ReceiptConfig,
    ReceiptError,
    _child_optional,
    _clp,
    _extract_original_ted,
    _fit,
    _optional,
    _parse,
    _pdf417,
    _required,
)


class InvoiceReceiptRenderer:
    """Renderiza DTE 33/34/52/56/61 sin reconstruir montos desde el negocio."""

    def render(self, signed_xml: bytes, config: ReceiptConfig) -> bytes:
        root = _parse(signed_xml)
        document_type = _required(root, "TipoDTE")
        if document_type not in {"33", "34", "52", "56", "61"}:
            raise ReceiptError("El DTE no admite representación carta nominativa")
        details = root.xpath("//*[local-name()='Detalle']")
        if not details or len(root.xpath("//*[local-name()='TED']")) != 1:
            raise ReceiptError("La factura debe contener detalle y un único TED")
        original_ted = _extract_original_ted(signed_xml)

        output = BytesIO()
        width, height = A4
        canvas = Canvas(output, pagesize=A4, pageCompression=1)
        margin = 18 * mm
        bottom = 22 * mm
        row_height = 6 * mm
        index = 0
        page = 1

        while index < len(details):
            y = self._header(canvas, root, width, height, margin, page)
            available = max(1, int((y - bottom - 55 * mm) / row_height))
            page_details = details[index:index + available]
            y = self._table_header(canvas, width, margin, y)
            for detail in page_details:
                name = _child_optional(detail, "NmbItem") or "SIN DESCRIPCIÓN"
                quantity = _child_optional(detail, "QtyItem") or "1"
                price = _child_optional(detail, "PrcItem") or "0"
                amount = _child_optional(detail, "MontoItem") or "0"
                canvas.setFont("Helvetica", 8)
                canvas.drawString(margin, y, _fit(name, 62))
                canvas.drawRightString(width - 70 * mm, y, quantity)
                canvas.drawRightString(width - 38 * mm, y, f"${_clp(price.split('.')[0])}")
                canvas.drawRightString(width - margin, y, f"${_clp(amount)}")
                y -= row_height
            index += len(page_details)
            if index < len(details):
                canvas.setFont("Helvetica-Oblique", 7)
                canvas.drawRightString(width - margin, bottom, "Continúa en página siguiente")
                canvas.showPage()
                page += 1
                continue

            self._totals_and_stamp(
                canvas,
                root,
                config,
                width,
                margin,
                y - 3 * mm,
                original_ted,
            )
            canvas.showPage()

        canvas.save()
        return output.getvalue()

    @staticmethod
    def _header(canvas, root, width, height, margin, page: int) -> float:
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(margin, height - 18 * mm, _required(root, "RznSoc"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(margin, height - 24 * mm, f"RUT {_required(root, 'RUTEmisor')}")
        canvas.drawString(margin, height - 29 * mm, _required(root, "GiroEmis"))
        address = " · ".join(
            value for value in (_optional(root, "DirOrigen"), _optional(root, "CmnaOrigen"))
            if value
        )
        if address:
            canvas.drawString(margin, height - 34 * mm, address)

        box_x = width - 78 * mm
        box_y = height - 40 * mm
        canvas.setLineWidth(1.1)
        canvas.rect(box_x, box_y, 60 * mm, 25 * mm)
        canvas.setFont("Helvetica-Bold", 9.5)
        title = {
            "33": "FACTURA ELECTRÓNICA",
            "34": "FACTURA EXENTA ELECTRÓNICA",
            "52": "GUÍA DE DESPACHO ELECTRÓNICA",
            "56": "NOTA DE DÉBITO ELECTRÓNICA",
            "61": "NOTA DE CRÉDITO ELECTRÓNICA",
        }[_required(root, "TipoDTE")]
        canvas.drawCentredString(box_x + 30 * mm, box_y + 17 * mm, title)
        canvas.drawCentredString(box_x + 30 * mm, box_y + 10 * mm, f"N° {_required(root, 'Folio')}")
        canvas.setFont("Helvetica", 7)
        canvas.drawCentredString(box_x + 30 * mm, box_y + 4 * mm, f"Página {page}")

        y = height - 50 * mm
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(margin, y, "Receptor")
        canvas.setFont("Helvetica", 8)
        y -= 6 * mm
        canvas.drawString(margin, y, f"{_required(root, 'RznSocRecep')} · RUT {_required(root, 'RUTRecep')}")
        y -= 5 * mm
        canvas.drawString(margin, y, _required(root, "GiroRecep"))
        y -= 5 * mm
        receiver_address = " · ".join(
            value for value in (_optional(root, "DirRecep"), _optional(root, "CmnaRecep"))
            if value
        )
        canvas.drawString(margin, y, receiver_address)
        canvas.drawRightString(width - margin, y, f"Emisión: {_required(root, 'FchEmis')}")
        destination = " · ".join(
            value for value in (_optional(root, "DirDest"), _optional(root, "CmnaDest"))
            if value
        )
        if destination:
            y -= 5 * mm
            canvas.drawString(margin, y, f"Destino: {destination}")
        return y - 10 * mm

    @staticmethod
    def _table_header(canvas, width, margin, y: float) -> float:
        canvas.setFillColorRGB(0.94, 0.95, 0.97)
        canvas.rect(margin, y - 2 * mm, width - 2 * margin, 7 * mm, stroke=0, fill=1)
        canvas.setFillColorRGB(0.08, 0.12, 0.2)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(margin + 2 * mm, y, "Detalle")
        canvas.drawRightString(width - 70 * mm, y, "Cantidad")
        canvas.drawRightString(width - 38 * mm, y, "Precio neto")
        canvas.drawRightString(width - margin - 2 * mm, y, "Monto")
        return y - 8 * mm

    @staticmethod
    def _totals_and_stamp(
        canvas,
        root,
        config,
        width,
        margin,
        y: float,
        original_ted: bytes,
    ) -> None:
        def total(label: str, tag: str, position: float, bold: bool = False) -> float:
            value = _optional(root, tag)
            if value is None:
                return position
            canvas.setFont("Helvetica-Bold" if bold else "Helvetica", 9)
            canvas.drawRightString(width - 55 * mm, position, label)
            canvas.drawRightString(width - margin, position, f"${_clp(value)}")
            return position - 5 * mm

        y = total("Neto", "MntNeto", y)
        y = total("Exento", "MntExe", y)
        y = total("IVA", "IVA", y)
        y = total("TOTAL", "MntTotal", y, True)

        barcode = _pdf417(original_ted)
        image_width, image_height = barcode.size
        stamp_width = 62 * mm
        stamp_height = stamp_width * image_height / image_width
        stamp_height = min(stamp_height, 27 * mm)
        canvas.drawImage(
            ImageReader(barcode),
            margin,
            max(18 * mm, y - stamp_height),
            stamp_width,
            stamp_height,
            preserveAspectRatio=True,
            mask="auto",
        )
        canvas.setFont("Helvetica", 7)
        canvas.drawString(margin, 14 * mm, f"Timbre electrónico SII · Res. {config.resolution_number} de {config.resolution_year}")
        canvas.drawRightString(width - margin, 14 * mm, f"Consulta: {config.verification_url}")
