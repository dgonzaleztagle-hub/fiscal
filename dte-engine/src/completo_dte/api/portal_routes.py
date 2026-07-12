"""Portal público de consulta de representaciones tributarias."""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from completo_dte.infrastructure import FolioLedger
from completo_dte.presentation import BoletaReceiptRenderer, ReceiptError


def register_public_portal_routes(
    *,
    app: FastAPI,
    ledger: FolioLedger,
    resolve_receipt_config: Callable[[str, str], Any] | None,
) -> None:
    @app.get("/public/v1/boletas/{public_id}", response_class=HTMLResponse)
    def public_receipt_page(public_id: str, request: Request) -> HTMLResponse:
        record = ledger.document_by_public_id(public_id)
        if record is None or resolve_receipt_config is None:
            raise HTTPException(status_code=404, detail="Boleta no encontrada")
        pdf_url = str(request.url_for("public_receipt_pdf", public_id=public_id))
        body = (
            '<!doctype html><html lang="es-CL"><head>'
            '<meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<meta name="robots" content="noindex,nofollow">'
            "<title>Boleta electrónica</title></head>"
            '<body style="font-family:system-ui;max-width:42rem;margin:3rem auto;padding:1rem">'
            "<h1>Boleta electrónica</h1>"
            f"<p>Emisor: {_html(record.taxpayer_rut)}</p>"
            f"<p>Tipo {record.document_type}, folio {record.folio}</p>"
            f"<p>Emitida: {_html(record.created_at[:10])}</p>"
            f'<p><a href="{_html(pdf_url)}">Ver representación de la boleta (PDF)</a></p>'
            "</body></html>"
        )
        return HTMLResponse(
            body,
            headers={
                "Cache-Control": "private, max-age=300",
                "X-Robots-Tag": "noindex",
            },
        )

    @app.get("/public/v1/boletas/{public_id}/pdf", name="public_receipt_pdf")
    def public_receipt_pdf(public_id: str) -> Response:
        record = ledger.document_by_public_id(public_id)
        if record is None or resolve_receipt_config is None:
            raise HTTPException(status_code=404, detail="Boleta no encontrada")
        try:
            config = resolve_receipt_config(record.tenant_id, record.taxpayer_rut)
            pdf = BoletaReceiptRenderer().render(record.signed_xml, config)
        except (ReceiptError, ValueError) as exc:
            raise HTTPException(
                status_code=503, detail="Representación no disponible"
            ) from exc
        return Response(
            pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="boleta-{record.folio}.pdf"',
                "Cache-Control": "private, max-age=300",
                "X-Robots-Tag": "noindex",
            },
        )


def _html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
