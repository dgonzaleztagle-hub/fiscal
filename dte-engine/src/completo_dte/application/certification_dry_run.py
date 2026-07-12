"""Ensayo offline reproducible de la ventana de certificación de boletas."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib
import io
import json
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from completo_dte.domain import (
    BoletaAfecta,
    BoletaLine,
    DailyFolio,
    DailySummaryBuilder,
    EnvelopeAuthorization,
    EnvioBoletaBuilder,
    Issuer,
    TedBuilder,
    TrustedCafAuthorization,
    XmlSigner,
    DteBuilder,
)


@dataclass(frozen=True)
class CertificationDryRunResult:
    document_count: int
    envelope_document_id: str
    rcof_document_id: str
    scenario: str
    final_state: str
    evidence_sha256: str
    evidence_zip: bytes
    manifest: dict[str, object]


class CertificationDryRunService:
    """Genera cinco DTE, sobre, RCOF y evidencia sin red ni folios reales."""

    SCENARIOS = {
        "accepted": "accepted",
        "timeout_after_upload": "unknown",
        "envelope_rejected": "rejected",
        "rcof_rejected": "rejected",
    }

    def __init__(
        self,
        *,
        issuer: Issuer,
        caf: TrustedCafAuthorization,
        credential,
        authorization: EnvelopeAuthorization,
    ) -> None:
        self._issuer = issuer
        self._caf = caf
        self._credential = credential
        self._authorization = authorization

    def run(
        self,
        *,
        issued_on: date,
        signed_at: datetime,
        scenario: str = "accepted",
    ) -> CertificationDryRunResult:
        if scenario not in self.SCENARIOS:
            raise ValueError("Escenario de certificación no soportado")
        if self._caf.data.folio_to - self._caf.data.folio_from + 1 < 5:
            raise ValueError("El ensayo necesita un CAF con al menos cinco folios")

        documents = []
        daily: list[DailyFolio] = []
        folio_from = self._caf.data.folio_from
        for index, lines in enumerate(_cases()):
            folio = folio_from + index
            boleta = BoletaAfecta(
                issuer=self._issuer,
                folio=folio,
                issued_on=issued_on,
                lines=lines,
                reference_code="SET",
                reference_reason=f"CASO-{index + 1}",
            )
            ted = TedBuilder().build(boleta, self._caf, generated_at=signed_at)
            unsigned = DteBuilder().build(boleta, ted, signed_at=signed_at)
            documents.append(XmlSigner().sign(unsigned, self._credential))
            daily.append(
                DailyFolio(
                    39,
                    folio,
                    issued_on,
                    boleta.net_total,
                    boleta.vat_total,
                    boleta.exempt_total,
                    boleta.total,
                )
            )

        envelope_id = f"SET_CERT_{issued_on:%Y%m%d}"
        envelope = EnvioBoletaBuilder().build(
            tuple(documents),
            issuer_rut=self._issuer.rut,
            sender_rut=self._issuer.rut,
            authorization=self._authorization,
            signed_at=signed_at,
            credential=self._credential,
            set_id=envelope_id,
        )
        rcof_id = f"RCOF_CERT_{issued_on:%Y%m%d}"
        rcof = DailySummaryBuilder().build(
            tuple(daily),
            issuer_rut=self._issuer.rut,
            sender_rut=self._issuer.rut,
            authorization=self._authorization,
            sequence=1,
            signed_at=signed_at,
            credential=self._credential,
            document_id=rcof_id,
        )
        artifacts = {
            **{
                f"dte/boleta-{folio_from + i}.xml": document.xml
                for i, document in enumerate(documents)
            },
            "sobres/envio-boleta.xml": envelope.xml,
            "sobres/rcof.xml": rcof.xml,
        }
        final_state = self.SCENARIOS[scenario]
        manifest: dict[str, object] = {
            "version": 1,
            "synthetic": True,
            "scenario": scenario,
            "final_state": final_state,
            "document_count": 5,
            "issuer_rut": self._issuer.rut,
            "issued_on": issued_on.isoformat(),
            "timeline": _timeline(scenario),
            "files": {
                name: {
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "bytes": len(content),
                }
                for name, content in sorted(artifacts.items())
            },
        }
        manifest_bytes = (
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode()
        archive = _archive({**artifacts, "manifest.json": manifest_bytes})
        return CertificationDryRunResult(
            document_count=5,
            envelope_document_id=envelope_id,
            rcof_document_id=rcof_id,
            scenario=scenario,
            final_state=final_state,
            evidence_sha256=hashlib.sha256(archive).hexdigest(),
            evidence_zip=archive,
            manifest=manifest,
        )


def _cases() -> tuple[tuple[BoletaLine, ...], ...]:
    return (
        (
            BoletaLine("Cambio de aceite", Decimal(1), Decimal(19900)),
            BoletaLine("Alineación", Decimal(1), Decimal(9900)),
        ),
        (BoletaLine("Papel de regalo", Decimal(17), Decimal(120)),),
        (
            BoletaLine("Sándwich", Decimal(2), Decimal(1500)),
            BoletaLine("Bebida", Decimal(2), Decimal(550)),
        ),
        (
            BoletaLine("Ítem afecto", Decimal(8), Decimal(1590)),
            BoletaLine("Ítem exento", Decimal(2), Decimal(1000), is_exempt=True),
        ),
        (BoletaLine("Arroz", Decimal(5), Decimal(700), unit_measure="Kg"),),
    )


def _timeline(scenario: str) -> list[dict[str, str]]:
    events = [
        {"step": "generate_five_documents", "state": "succeeded"},
        {"step": "build_envelope", "state": "succeeded"},
        {"step": "build_rcof", "state": "succeeded"},
    ]
    if scenario == "timeout_after_upload":
        return events + [
            {"step": "upload_envelope", "state": "unknown"},
            {"step": "reconcile", "state": "required"},
        ]
    if scenario == "envelope_rejected":
        return events + [{"step": "upload_envelope", "state": "rejected"}]
    if scenario == "rcof_rejected":
        return events + [
            {"step": "upload_envelope", "state": "accepted"},
            {"step": "upload_rcof", "state": "rejected"},
        ]
    return events + [
        {"step": "upload_envelope", "state": "accepted"},
        {"step": "upload_rcof", "state": "accepted"},
    ]


def _archive(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, content)
    return output.getvalue()
