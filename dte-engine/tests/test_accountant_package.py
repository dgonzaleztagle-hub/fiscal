from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
from zipfile import ZipFile

from completo_dte.application import (
    AccountantPackageBuilder,
    IssueInvoiceService,
    MonthlyReportBuilder,
    MonthlyDossierBuilder,
)
from test_issue_invoice import setup_invoice
from test_received_ledger import received_document


def test_accountant_package_contains_original_xml_reports_and_hash_manifest(tmp_path) -> None:
    ledger, caf, _caf_id, credential, command = setup_invoice(tmp_path)
    sale = IssueInvoiceService(
        ledger=ledger,
        resolve_caf=lambda _requested: caf,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 10, 15, 30, tzinfo=timezone.utc),
    ).issue(command)
    purchase = ledger.import_received_document(
        tenant_id="tenant-a", document=received_document(), source="upload"
    )
    report = MonthlyReportBuilder().build(
        year=2026, month=7, outgoing=[sale], received=[purchase]
    )
    dossier = MonthlyDossierBuilder().build(
        report=report,
        close_snapshot_id="close-v1",
        close_calculation_sha256="b" * 64,
        rcv_snapshot_id="rcv-v1",
        rcv_payload_sha256="c" * 64,
    )
    package = AccountantPackageBuilder().build(
        report=report, outgoing=[sale], received=[purchase], dossier=dossier
    )
    assert package.sha256 == hashlib.sha256(package.content).hexdigest()
    with ZipFile(BytesIO(package.content)) as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        assert any(name.endswith(".xlsx") for name in names)
        assert any(name.startswith("xml/ventas/") for name in names)
        assert any(name.startswith("xml/compras/") for name in names)
        assert "expediente/expediente.json" in names
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["dossier_evidence_sha256"] == dossier.evidence_hash
        for name, evidence in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == evidence["sha256"]
