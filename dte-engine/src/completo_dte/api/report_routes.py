"""Rutas de reportes fiscales y paquete para contador."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response

from completo_dte.application import (
    AccountantPackageBuilder,
    MonthlyCloseCalculator,
    MonthlyCloseInputs,
    MonthlyDossierBuilder,
    MonthlyReportBuilder,
)
from completo_dte.domain import RcvPeriod
from completo_dte.infrastructure import FolioLedger, FolioLedgerError, RcvRepository

from .contracts import MonthlyCloseRequest, MonthlyCloseReviewRequest
from .security import ApiPrincipal


def register_report_routes(
    *,
    app: FastAPI,
    ledger: FolioLedger,
    authenticate: Callable[..., ApiPrincipal],
    rcv_repository: RcvRepository | None = None,
) -> None:
    @app.get("/v1/reports/monthly/{year}/{month}/dossier")
    def get_monthly_dossier(
        year: int,
        month: int,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> dict[str, Any]:
        try:
            outgoing, received = _load_period_records(
                ledger, principal.tenant_id, year, month
            )
            report = MonthlyReportBuilder().build(
                year=year, month=month, outgoing=outgoing, received=received
            )
            closes = ledger.list_monthly_closes(
                tenant_id=principal.tenant_id, period=report.period
            )
            close = closes[0] if closes else None
            rcv = (
                rcv_repository.latest_snapshot(
                    tenant_id=principal.tenant_id, period=RcvPeriod(year, month)
                )
                if rcv_repository is not None
                else None
            )
            dossier = MonthlyDossierBuilder().build(
                report=report,
                close_snapshot_id=close.id if close else None,
                close_calculation_sha256=close.calculation_sha256 if close else None,
                rcv_snapshot_id=rcv.id if rcv else None,
                rcv_payload_sha256=rcv.payload_sha256 if rcv else None,
                payment_reconciliation_ref=(
                    payment.id
                    if (payment := ledger.latest_payment_reconciliation(
                        tenant_id=principal.tenant_id, period=report.period
                    ))
                    else None
                ),
                payment_reconciliation_ready=(
                    bool(payment.payload.get("ready")) if payment else None
                ),
                people_summary_ref=(
                    people.id
                    if (people := ledger.latest_people_summary(
                        tenant_id=principal.tenant_id, period=report.period
                    ))
                    else None
                ),
            )
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "period": dossier.period,
            "ready": dossier.ready,
            "ready_count": dossier.ready_count,
            "total_count": len(dossier.items),
            "evidence_hash": dossier.evidence_hash,
            "items": [
                {
                    "code": item.code,
                    "label": item.label,
                    "state": item.state.value,
                    "detail": item.detail,
                    "source_ref": item.source_ref,
                    "source_sha256": item.source_sha256,
                }
                for item in dossier.items
            ],
        }

    @app.post("/v1/reports/monthly/{year}/{month}/close")
    def calculate_monthly_close(
        year: int,
        month: int,
        payload: MonthlyCloseRequest,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> dict[str, Any]:
        try:
            outgoing, received = _load_period_records(
                ledger, principal.tenant_id, year, month
            )
            report = MonthlyReportBuilder().build(
                year=year, month=month, outgoing=outgoing, received=received
            )
            close_inputs = payload.model_dump()
            people = ledger.latest_people_summary(
                tenant_id=principal.tenant_id, period=report.period
            )
            if people is not None:
                close_inputs["single_tax"] = people.payload["single_tax"]
                close_inputs["additional_withholding"] = people.payload[
                    "other_withholdings"
                ]
            snapshot = MonthlyCloseCalculator().calculate(
                report, MonthlyCloseInputs(**close_inputs)
            )
            response_payload = _snapshot_response(snapshot)
            stored = ledger.persist_monthly_close(
                tenant_id=principal.tenant_id,
                period=snapshot.period,
                formula_version=snapshot.formula_version,
                source_sha256=snapshot.source_hash,
                calculation_sha256=snapshot.calculation_hash,
                payload=response_payload,
            )
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {**response_payload, "snapshot_id": stored.id, "version": stored.version}

    @app.get("/v1/reports/monthly/{year}/{month}/close/snapshots")
    def list_monthly_close_snapshots(
        year: int,
        month: int,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[dict[str, Any]]:
        period = RcvPeriod(year, month)
        records = ledger.list_monthly_closes(
            tenant_id=principal.tenant_id,
            period=f"{period.year:04d}-{period.month:02d}",
        )
        return [
            {
                "snapshot_id": record.id,
                "version": record.version,
                "formula_version": record.formula_version,
                "source_hash": record.source_sha256,
                "calculation_hash": record.calculation_sha256,
                "created_at": record.created_at,
                "payload": record.payload,
            }
            for record in records
        ]

    @app.post("/v1/reports/monthly/close/snapshots/{snapshot_id}/reviews")
    def review_monthly_close(
        snapshot_id: str,
        payload: MonthlyCloseReviewRequest,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> dict[str, Any]:
        try:
            record = ledger.review_monthly_close(
                tenant_id=principal.tenant_id,
                snapshot_id=snapshot_id,
                actor_ref=f"authenticated-tenant:{principal.tenant_id}",
                action=payload.action,
                reason=payload.reason,
            )
        except FolioLedgerError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "id": record.id,
            "snapshot_id": record.snapshot_id,
            "action": record.action,
            "actor_ref": record.actor_ref,
            "reason": record.reason,
            "occurred_at": record.occurred_at,
        }

    @app.get("/v1/reports/monthly/{year}/{month}.csv")
    def export_monthly_csv(
        year: int,
        month: int,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> Response:
        try:
            outgoing, received = _load_period_records(
                ledger, principal.tenant_id, year, month
            )
            builder = MonthlyReportBuilder()
            report = builder.build(
                year=year,
                month=month,
                outgoing=outgoing,
                received=received,
            )
            artifact = builder.csv(report)
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(
            artifact.content,
            media_type=artifact.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{artifact.filename}"',
                "X-Content-SHA256": artifact.sha256,
                "Cache-Control": "private, no-store",
            },
        )

    @app.get("/v1/reports/monthly/{year}/{month}.xlsx")
    def export_monthly_xlsx(
        year: int,
        month: int,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> Response:
        try:
            outgoing, received = _load_period_records(
                ledger, principal.tenant_id, year, month
            )
            builder = MonthlyReportBuilder()
            artifact = builder.xlsx(
                builder.build(
                    year=year,
                    month=month,
                    outgoing=outgoing,
                    received=received,
                )
            )
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(
            artifact.content,
            media_type=artifact.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{artifact.filename}"',
                "X-Content-SHA256": artifact.sha256,
                "Cache-Control": "private, no-store",
            },
        )

    @app.get("/v1/reports/monthly/{year}/{month}.pdf")
    def export_monthly_pdf(
        year: int,
        month: int,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> Response:
        try:
            outgoing, received = _load_period_records(
                ledger, principal.tenant_id, year, month
            )
            builder = MonthlyReportBuilder()
            artifact = builder.pdf(
                builder.build(
                    year=year, month=month, outgoing=outgoing, received=received
                )
            )
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(
            artifact.content,
            media_type=artifact.media_type,
            headers={
                "Content-Disposition": f'inline; filename="{artifact.filename}"',
                "X-Content-SHA256": artifact.sha256,
                "Cache-Control": "private, no-store",
            },
        )

    @app.get("/v1/reports/monthly/{year}/{month}/accountant-package.zip")
    def export_accountant_package(
        year: int,
        month: int,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> Response:
        try:
            outgoing, received = _load_period_records(
                ledger, principal.tenant_id, year, month
            )
            report = MonthlyReportBuilder().build(
                year=year, month=month, outgoing=outgoing, received=received
            )
            closes = ledger.list_monthly_closes(
                tenant_id=principal.tenant_id, period=report.period
            )
            close = closes[0] if closes else None
            rcv = (
                rcv_repository.latest_snapshot(
                    tenant_id=principal.tenant_id, period=RcvPeriod(year, month)
                )
                if rcv_repository is not None
                else None
            )
            dossier = MonthlyDossierBuilder().build(
                report=report,
                close_snapshot_id=close.id if close else None,
                close_calculation_sha256=close.calculation_sha256 if close else None,
                rcv_snapshot_id=rcv.id if rcv else None,
                rcv_payload_sha256=rcv.payload_sha256 if rcv else None,
                payment_reconciliation_ref=(
                    payment.id
                    if (payment := ledger.latest_payment_reconciliation(
                        tenant_id=principal.tenant_id, period=report.period
                    ))
                    else None
                ),
                people_summary_ref=(
                    people.id
                    if (people := ledger.latest_people_summary(
                        tenant_id=principal.tenant_id, period=report.period
                    ))
                    else None
                ),
            )
            package = AccountantPackageBuilder().build(
                report=report,
                outgoing=outgoing,
                received=received,
                dossier=dossier,
            )
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(
            package.content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{package.filename}"',
                "X-Content-SHA256": package.sha256,
                "Cache-Control": "private, no-store",
            },
        )


def _load_period_records(
    ledger: FolioLedger,
    tenant_id: str,
    year: int,
    month: int,
) -> tuple[list[Any], list[Any]]:
    """Valida el período y recorre todas las páginas sin truncar el informe."""
    RcvPeriod(year, month)
    outgoing = _all_pages(
        lambda limit, offset: ledger.list_documents(
            tenant_id=tenant_id, limit=limit, offset=offset
        )
    )
    received = _all_pages(
        lambda limit, offset: ledger.list_received_documents(
            tenant_id=tenant_id, limit=limit, offset=offset
        )
    )
    return outgoing, received


def _all_pages(fetch: Callable[[int, int], tuple[Any, ...]]) -> list[Any]:
    records: list[Any] = []
    offset = 0
    while True:
        page = fetch(200, offset)
        records.extend(page)
        if len(page) < 200:
            return records
        offset += 200


def _snapshot_response(snapshot) -> dict[str, Any]:
    return {
        "period": snapshot.period,
        "formula_version": snapshot.formula_version,
        "source_hash": snapshot.source_hash,
        "calculation_hash": snapshot.calculation_hash,
        "sales": {
            "net": snapshot.sales_net,
            "exempt": snapshot.sales_exempt,
            "vat": snapshot.sales_vat,
            "total": snapshot.sales_total,
        },
        "purchases": {
            "net": snapshot.purchases_net,
            "exempt": snapshot.purchases_exempt,
            "vat": snapshot.purchases_vat,
            "total": snapshot.purchases_total,
        },
        "ppm_basis": snapshot.ppm_basis,
        "ppm": snapshot.ppm,
        "vat_payable": snapshot.vat_payable,
        "next_vat_credit": snapshot.next_vat_credit,
        "total_payable": snapshot.total_payable,
        "lines": [
            {
                "code": line.code,
                "label": line.label,
                "amount": line.amount,
                "sii_amount": line.sii_amount,
                "difference": line.difference,
                "state": line.state.value,
            }
            for line in snapshot.lines
        ],
        "notice": "Propuesta informativa; no presenta ni rectifica el F29",
    }
