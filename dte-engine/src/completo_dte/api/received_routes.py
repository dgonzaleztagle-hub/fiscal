"""Rutas de recepción, decisión y clasificación de compras."""

from collections.abc import Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from completo_dte.application import ReceivedDecisionService
from completo_dte.domain import (
    PurchaseLineAllocation,
    ReceivedDecision,
    ReceivedDecisionError,
    ReceivedDocumentError,
    ReceivedDocumentValidator,
)
from completo_dte.infrastructure import FolioLedger, FolioLedgerError

from .contracts import (
    PurchaseAllocationsRequest,
    ReceivedClassificationRequest,
    ReceivedClassificationResponse,
    ReceivedDecisionRequest,
    ReceivedDecisionResponse,
    ReceivedDocumentResponse,
)
from .projections import (
    _received_classification_response,
    _received_decision_response,
    _received_response,
)
from .security import ApiPrincipal


def register_received_routes(
    *,
    app: FastAPI,
    ledger: FolioLedger,
    authenticate: Callable[..., ApiPrincipal],
    received_document_validator: ReceivedDocumentValidator | None,
    resolve_tenant_taxpayer_rut: Callable[[str], str] | None,
    received_decision_service: ReceivedDecisionService | None,
) -> None:
    @app.post(
        "/v1/received-documents/import",
        response_model=ReceivedDocumentResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def import_received_document(
        request: Request,
        source: str = "upload",
        principal: ApiPrincipal = Depends(authenticate),
    ) -> ReceivedDocumentResponse:
        if received_document_validator is None or resolve_tenant_taxpayer_rut is None:
            raise HTTPException(
                status_code=503, detail="La recepción no está configurada"
            )
        if request.headers.get("content-type", "").split(";", 1)[0] not in {
            "application/xml",
            "text/xml",
        }:
            raise HTTPException(status_code=415, detail="Se requiere XML tributario")
        try:
            expected_rut = resolve_tenant_taxpayer_rut(principal.tenant_id)
            received = received_document_validator.validate(
                await request.body(), expected_receiver_rut=expected_rut
            )
            record = ledger.import_received_document(
                tenant_id=principal.tenant_id,
                document=received,
                source=source,
            )
        except ReceivedDocumentError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except FolioLedgerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _received_response(record)

    @app.get(
        "/v1/received-documents",
        response_model=list[ReceivedDocumentResponse],
    )
    def list_received_documents(
        document_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[ReceivedDocumentResponse]:
        try:
            records = ledger.list_received_documents(
                tenant_id=principal.tenant_id,
                status=document_status,
                limit=limit,
                offset=offset,
            )
        except FolioLedgerError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return [_received_response(record) for record in records]

    @app.post(
        "/v1/received-documents/{record_id}/decision",
        response_model=ReceivedDecisionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def decide_received_document(
        record_id: str,
        payload: ReceivedDecisionRequest,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> ReceivedDecisionResponse:
        if received_decision_service is None:
            raise HTTPException(
                status_code=503, detail="Las decisiones no están configuradas"
            )
        try:
            prepared = received_decision_service.prepare(
                tenant_id=principal.tenant_id,
                received_document_id=record_id,
                intent=ReceivedDecision(payload.decision, payload.reason),
            )
            final = (
                received_decision_service.submit(prepared)
                if prepared.status.value == "prepared"
                else prepared
            )
        except ReceivedDecisionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except FolioLedgerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _received_decision_response(final)

    @app.post(
        "/v1/received-decisions/{decision_id}/reconcile",
        response_model=ReceivedDecisionResponse,
    )
    def reconcile_received_decision(
        decision_id: str,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> ReceivedDecisionResponse:
        if received_decision_service is None:
            raise HTTPException(
                status_code=503, detail="Las decisiones no están configuradas"
            )
        decision = ledger.received_decision_by_id(
            decision_id, tenant_id=principal.tenant_id
        )
        if decision is None:
            raise HTTPException(status_code=404, detail="Decisión no encontrada")
        try:
            final = received_decision_service.reconcile(decision)
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _received_decision_response(final)

    @app.post(
        "/v1/received-documents/{record_id}/classification",
        response_model=ReceivedClassificationResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def classify_received_document(
        record_id: str,
        payload: ReceivedClassificationRequest,
        principal: ApiPrincipal = Depends(authenticate),
        actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    ) -> ReceivedClassificationResponse:
        if not actor_id:
            raise HTTPException(status_code=400, detail="X-Actor-Id es obligatorio")
        try:
            record = ledger.classify_received_document(
                tenant_id=principal.tenant_id,
                received_document_id=record_id,
                provider_id=payload.provider_id,
                destination=payload.destination,
                category_code=payload.category_code,
                notes=payload.notes,
                classified_by=actor_id,
            )
        except FolioLedgerError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _received_classification_response(record)

    @app.get(
        "/v1/received-documents/{record_id}/classification",
        response_model=ReceivedClassificationResponse | None,
    )
    def get_received_classification(
        record_id: str,
        principal: ApiPrincipal = Depends(authenticate),
    ):
        record = ledger.latest_received_classification(
            record_id, tenant_id=principal.tenant_id
        )
        return _received_classification_response(record) if record else None

    @app.post(
        "/v1/received-classifications/{classification_id}/line-allocations",
        status_code=status.HTTP_201_CREATED,
    )
    def allocate_received_lines(
        classification_id: str,
        payload: PurchaseAllocationsRequest,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[dict[str, object]]:
        try:
            records = ledger.allocate_received_lines(
                tenant_id=principal.tenant_id,
                classification_id=classification_id,
                allocations=tuple(
                    PurchaseLineAllocation(**item.model_dump())
                    for item in payload.allocations
                ),
            )
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return [
            {
                "classification_id": record.classification_id,
                "line_number": record.line_number,
                "destination": record.destination,
                "control_plane_ref": record.control_plane_ref,
            }
            for record in records
        ]
