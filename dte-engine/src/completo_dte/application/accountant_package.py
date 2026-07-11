"""Paquete autocontenido para contador con manifiesto verificable."""

from dataclasses import dataclass
from io import BytesIO
import hashlib
import json
from zipfile import ZIP_DEFLATED, ZipFile

from completo_dte.infrastructure import FiscalDocumentRecord, ReceivedFiscalDocumentRecord
from .monthly_report import MonthlyFiscalReport, MonthlyReportBuilder


@dataclass(frozen=True)
class AccountantPackage:
    filename: str
    content: bytes
    sha256: str


class AccountantPackageBuilder:
    def build(
        self,
        *,
        report: MonthlyFiscalReport,
        outgoing: list[FiscalDocumentRecord],
        received: list[ReceivedFiscalDocumentRecord],
    ) -> AccountantPackage:
        reports = MonthlyReportBuilder()
        artifacts = [reports.csv(report), reports.xlsx(report), reports.pdf(report)]
        files: dict[str, bytes] = {
            f"reportes/{artifact.filename}": artifact.content for artifact in artifacts
        }
        for record in outgoing:
            files[f"xml/ventas/{record.document_type}-{record.folio}-{record.xml_sha256[:12]}.xml"] = record.signed_xml
        for record in received:
            files[f"xml/compras/{record.document_type}-{record.folio}-{record.xml_sha256[:12]}.xml"] = record.signed_xml
        manifest = {
            "period": report.period,
            "files": {
                name: {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
                for name, content in sorted(files.items())
            },
        }
        files["manifest.json"] = (
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            for name, content in sorted(files.items()):
                archive.writestr(name, content)
        content = output.getvalue()
        return AccountantPackage(
            f"completo-fiscal-contador-{report.period}.zip",
            content,
            hashlib.sha256(content).hexdigest(),
        )
