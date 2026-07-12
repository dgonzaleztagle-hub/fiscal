"""Rutas de importación y conciliación del Registro de Compras y Ventas."""

from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException, status

from completo_dte.application import RcvReconciliationService
from completo_dte.domain import RcvPeriod, RcvPurchaseEntry
from completo_dte.infrastructure import FolioLedgerError, RcvRepository

from .contracts import RcvDifferenceResponse, RcvImportRequest, RcvSnapshotResponse
from .projections import _rcv_snapshot_response
from .security import ApiPrincipal


def register_rcv_routes(
    *,
    app: FastAPI,
    authenticate: Callable[..., ApiPrincipal],
    rcv_repository: RcvRepository | None,
    rcv_reconciliation_service: RcvReconciliationService | None,
) -> None:
    @app.post(
        "/v1/rcv/purchases/snapshots",
        response_model=RcvSnapshotResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def import_rcv_snapshot(
        payload: RcvImportRequest,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> RcvSnapshotResponse:
        if rcv_repository is None:
            raise HTTPException(status_code=503, detail="RCV no está configurado")
        try:
            snapshot = rcv_repository.import_snapshot(
                tenant_id=principal.tenant_id,
                period=RcvPeriod(payload.year, payload.month),
                entries=tuple(
                    RcvPurchaseEntry(**entry.model_dump()) for entry in payload.entries
                ),
                source=payload.source,
            )
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _rcv_snapshot_response(snapshot)

    @app.get(
        "/v1/rcv/purchases/{year}/{month}/reconciliation",
        response_model=list[RcvDifferenceResponse],
    )
    def reconcile_rcv_snapshot(
        year: int,
        month: int,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[RcvDifferenceResponse]:
        if rcv_repository is None or rcv_reconciliation_service is None:
            raise HTTPException(status_code=503, detail="RCV no está configurado")
        try:
            period = RcvPeriod(year, month)
            snapshot = rcv_repository.latest_snapshot(
                tenant_id=principal.tenant_id, period=period
            )
            if snapshot is None:
                raise HTTPException(
                    status_code=404, detail="Snapshot RCV no encontrado"
                )
            differences = rcv_reconciliation_service.reconcile(
                tenant_id=principal.tenant_id, snapshot=snapshot
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return [
            RcvDifferenceResponse(**difference.__dict__) for difference in differences
        ]
