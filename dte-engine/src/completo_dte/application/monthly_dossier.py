"""Expediente mensual: inventario explicable de evidencia, sin inventar fuentes."""

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json

from .monthly_report import MonthlyFiscalReport


class EvidenceState(StrEnum):
    READY = "ready"
    REVIEW = "review"
    MISSING = "missing"
    NOT_CONNECTED = "not_connected"


@dataclass(frozen=True)
class EvidenceItem:
    code: str
    label: str
    state: EvidenceState
    detail: str
    source_ref: str | None = None
    source_sha256: str | None = None


@dataclass(frozen=True)
class MonthlyDossier:
    period: str
    ready: bool
    evidence_hash: str
    items: tuple[EvidenceItem, ...]

    @property
    def ready_count(self) -> int:
        return sum(item.state is EvidenceState.READY for item in self.items)


class MonthlyDossierBuilder:
    def build(
        self,
        *,
        report: MonthlyFiscalReport,
        close_snapshot_id: str | None,
        close_calculation_sha256: str | None,
        rcv_snapshot_id: str | None,
        rcv_payload_sha256: str | None,
        bhe_snapshot_ref: str | None = None,
        people_summary_ref: str | None = None,
        payment_reconciliation_ref: str | None = None,
        payment_reconciliation_ready: bool | None = None,
    ) -> MonthlyDossier:
        document_hash = _document_evidence_hash(report)
        items = (
            EvidenceItem(
                "documents",
                "Ventas y compras documentadas",
                EvidenceState.READY,
                f"{sum(row.direction == 'sale' for row in report.rows)} ventas y "
                f"{sum(row.direction == 'purchase' for row in report.rows)} compras en ledger",
                source_ref=report.period,
                source_sha256=document_hash,
            ),
            _item(
                "rcv",
                "Registro de Compras y Ventas",
                rcv_snapshot_id,
                rcv_payload_sha256,
                "No existe snapshot RCV para comparar el período",
            ),
            _item(
                "close",
                "Cierre mensual calculado",
                close_snapshot_id,
                close_calculation_sha256,
                "El período todavía no tiene una versión calculada",
            ),
            _item(
                "bhe",
                "Boletas de honorarios",
                bhe_snapshot_ref,
                None,
                "El conector BHE aún no entregó una versión del período",
                absent=EvidenceState.NOT_CONNECTED,
            ),
            _item(
                "people",
                "Resumen de Personas",
                people_summary_ref,
                None,
                "Completo Personas aún no entregó su resumen mensual",
                absent=EvidenceState.NOT_CONNECTED,
            ),
            _payment_item(payment_reconciliation_ref, payment_reconciliation_ready),
        )
        payload = [
            {
                "code": item.code,
                "state": item.state.value,
                "source_ref": item.source_ref,
                "source_sha256": item.source_sha256,
            }
            for item in items
        ]
        evidence_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        blocking = {EvidenceState.MISSING, EvidenceState.REVIEW}
        return MonthlyDossier(
            report.period,
            not any(item.state in blocking for item in items),
            evidence_hash,
            items,
        )


def _item(
    code: str,
    label: str,
    reference: str | None,
    digest: str | None,
    missing_detail: str,
    *,
    absent: EvidenceState = EvidenceState.MISSING,
) -> EvidenceItem:
    if reference is None:
        return EvidenceItem(code, label, absent, missing_detail)
    return EvidenceItem(code, label, EvidenceState.READY, "Fuente versionada disponible", reference, digest)


def _document_evidence_hash(report: MonthlyFiscalReport) -> str:
    hashes = sorted(row.xml_sha256 for row in report.rows)
    return hashlib.sha256("\n".join(hashes).encode()).hexdigest()


def _payment_item(reference: str | None, ready: bool | None) -> EvidenceItem:
    if reference is None:
        return EvidenceItem("payments", "Pagos electrónicos", EvidenceState.NOT_CONNECTED,
                            "Vouchers y liquidaciones aún no fueron conciliados")
    if ready is not True:
        return EvidenceItem("payments", "Pagos electrónicos", EvidenceState.REVIEW,
                            "La conciliación tiene diferencias pendientes", reference)
    return EvidenceItem("payments", "Pagos electrónicos", EvidenceState.READY,
                        "Conciliación sin diferencias", reference)
