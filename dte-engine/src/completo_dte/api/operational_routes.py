"""Rutas operacionales de documentos, entregas, sobres y alertas."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import Response

from completo_dte.application import InvoiceDeliveryService
from completo_dte.infrastructure import FolioLedger, FolioLedgerError
from completo_dte.presentation import (
    BoletaReceiptRenderer,
    InvoiceReceiptRenderer,
    ReceiptError,
)

from .contracts import (
    DeliveryRequest,
    DeliveryResponse,
    EnvelopeResponse,
    EventResponse,
    OperationalAlertResponse,
)
from .projections import _delivery_response
from .security import ApiPrincipal


def register_operational_routes(
    *,
    app: FastAPI,
    ledger: FolioLedger,
    authenticate: Callable[..., ApiPrincipal],
    resolve_receipt_config: Callable[[str, str], Any] | None,
    invoice_delivery_service: InvoiceDeliveryService | None,
) -> None:
    @app.get(
        "/v1/fiscal-documents/{record_id}/events",
        response_model=list[EventResponse],
    )
    def get_document_events(
        record_id: str,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[EventResponse]:
        record = ledger.document_by_id(record_id, tenant_id=principal.tenant_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        return [EventResponse(**event) for event in ledger.events(record.lease_id)]

    @app.get("/v1/fiscal-documents/{record_id}/pdf")
    def get_document_pdf(
        record_id: str,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> Response:
        record = ledger.document_by_id(record_id, tenant_id=principal.tenant_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        if resolve_receipt_config is None or record.document_type not in {
            33,
            34,
            39,
            41,
            52,
            56,
            61,
        }:
            raise HTTPException(status_code=503, detail="Representación no disponible")
        try:
            config = resolve_receipt_config(record.tenant_id, record.taxpayer_rut)
            renderer = (
                BoletaReceiptRenderer()
                if record.document_type in {39, 41}
                else InvoiceReceiptRenderer()
            )
            pdf = renderer.render(record.signed_xml, config)
        except (ReceiptError, ValueError) as exc:
            raise HTTPException(
                status_code=503, detail="Representación no disponible"
            ) from exc
        return Response(
            pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{record.document_id}.pdf"',
                "Cache-Control": "private, no-store",
            },
        )

    @app.post(
        "/v1/fiscal-documents/{record_id}/deliveries",
        response_model=DeliveryResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def queue_invoice_delivery(
        record_id: str,
        payload: DeliveryRequest,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> DeliveryResponse:
        if invoice_delivery_service is None:
            raise HTTPException(
                status_code=503,
                detail="La entrega de facturas no está configurada en este entorno",
            )
        record = ledger.document_by_id(record_id, tenant_id=principal.tenant_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        try:
            delivery = invoice_delivery_service.queue(
                record,
                recipient_email=payload.recipient_email,
            )
        except (FolioLedgerError, ReceiptError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _delivery_response(delivery)

    @app.get(
        "/v1/fiscal-deliveries/{delivery_id}",
        response_model=DeliveryResponse,
    )
    def get_fiscal_delivery(
        delivery_id: str,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> DeliveryResponse:
        delivery = ledger.delivery_by_id(delivery_id, tenant_id=principal.tenant_id)
        if delivery is None:
            raise HTTPException(status_code=404, detail="Entrega no encontrada")
        return _delivery_response(delivery)

    @app.get("/v1/fiscal-envelopes", response_model=list[EnvelopeResponse])
    def list_fiscal_envelopes(
        limit: int = 100,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[EnvelopeResponse]:
        try:
            envelopes = ledger.list_envelopes(
                tenant_id=principal.tenant_id,
                limit=limit,
            )
        except FolioLedgerError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return [
            EnvelopeResponse(
                **{
                    "id": envelope.id,
                    "kind": envelope.kind,
                    "document_id": envelope.document_id,
                    "taxpayer_rut": envelope.taxpayer_rut,
                    "status": envelope.status.value,
                    "track_id": envelope.track_id,
                    "xml_sha256": envelope.xml_sha256,
                    "created_at": envelope.created_at,
                    "updated_at": envelope.updated_at,
                }
            )
            for envelope in envelopes
        ]

    @app.get(
        "/v1/operational-alerts",
        response_model=list[OperationalAlertResponse],
    )
    def operational_alerts(
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[OperationalAlertResponse]:
        return [
            OperationalAlertResponse(**alert)
            for alert in ledger.operational_alerts(tenant_id=principal.tenant_id)
        ]
