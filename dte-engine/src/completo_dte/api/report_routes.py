"""Rutas de reportes fiscales y paquete para contador."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response

from completo_dte.application import AccountantPackageBuilder, MonthlyReportBuilder
from completo_dte.domain import RcvPeriod
from completo_dte.infrastructure import FolioLedger, FolioLedgerError

from .security import ApiPrincipal


def register_report_routes(
    *,
    app: FastAPI,
    ledger: FolioLedger,
    authenticate: Callable[..., ApiPrincipal],
) -> None:
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
            package = AccountantPackageBuilder().build(
                report=report, outgoing=outgoing, received=received
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
