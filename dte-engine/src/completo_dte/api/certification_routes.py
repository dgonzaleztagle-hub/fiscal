"""Cockpit y ensayo offline de certificación."""

from collections.abc import Callable
from datetime import date, datetime, timezone

from fastapi import Depends, FastAPI, HTTPException

from completo_dte.application import CertificationDryRunService

from .contracts import (
    CertificationDryRunRequest,
    CertificationDryRunResponse,
    CertificationReadinessResponse,
)
from .security import ApiPrincipal


def register_certification_routes(
    *,
    app: FastAPI,
    authenticate: Callable[..., ApiPrincipal],
    dry_run_service: CertificationDryRunService | None,
) -> None:
    @app.get(
        "/v1/certification/readiness", response_model=CertificationReadinessResponse
    )
    def readiness(
        _principal: ApiPrincipal = Depends(authenticate),
    ) -> CertificationReadinessResponse:
        gates = [
            _gate(
                "offline_engine",
                "Motor y regresión documental",
                dry_run_service is not None,
                "DTE 33/34/39/41/52/56/61 y firmas locales",
            ),
            _gate(
                "dry_run",
                "Ensayo de cinco folios",
                dry_run_service is not None,
                "Sobre, RCOF, fallas y evidencia sintética",
            ),
            _gate(
                "public_https",
                "Consulta pública HTTPS",
                False,
                "Requiere despliegue accesible antes de certificar",
            ),
            _gate(
                "real_certificate",
                "Certificado digital real",
                False,
                "Pendiente de compra y carga en vault",
            ),
            _gate(
                "real_caf",
                "CAF real de cinco folios",
                False,
                "Bloqueado para no iniciar la ventana de 24 horas",
            ),
        ]
        completed = sum(bool(gate["completed"]) for gate in gates)
        return CertificationReadinessResponse(
            ready_to_download_caf=completed == len(gates),
            completed=completed,
            total=len(gates),
            gates=gates,
        )

    @app.post("/v1/certification/dry-runs", response_model=CertificationDryRunResponse)
    def run_dry_run(
        payload: CertificationDryRunRequest,
        _principal: ApiPrincipal = Depends(authenticate),
    ) -> CertificationDryRunResponse:
        if dry_run_service is None:
            raise HTTPException(status_code=503, detail="Ensayo offline no configurado")
        try:
            result = dry_run_service.run(
                issued_on=date(2026, 7, 12),
                signed_at=datetime(2026, 7, 12, 12, tzinfo=timezone.utc),
                scenario=payload.scenario,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return CertificationDryRunResponse(
            synthetic=True,
            document_count=result.document_count,
            envelope_document_id=result.envelope_document_id,
            rcof_document_id=result.rcof_document_id,
            scenario=result.scenario,
            final_state=result.final_state,
            evidence_sha256=result.evidence_sha256,
            timeline=result.manifest["timeline"],
        )


def _gate(code: str, title: str, completed: bool, detail: str) -> dict[str, object]:
    return {"code": code, "title": title, "completed": completed, "detail": detail}
