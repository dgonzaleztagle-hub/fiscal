from datetime import date, datetime, timezone
import hashlib
import io
import json
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from completo_dte.application import CertificationDryRunService
from completo_dte.domain import EnvelopeAuthorization, Issuer
from factories import make_signing_credential, make_trusted_caf
from completo_dte.api.demo import DEMO_TOKEN, create_demo_app


def service() -> CertificationDryRunService:
    return CertificationDryRunService(
        issuer=Issuer(
            rut="12345678-5",
            legal_name="EMISOR SINTETICO SPA",
            business_activity="RESTAURANTES",
            activity_code=561000,
            address="CALLE UNO 123",
            commune="SANTIAGO",
        ),
        caf=make_trusted_caf(folio_from=1, folio_to=5),
        credential=make_signing_credential(),
        authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
    )


@pytest.mark.parametrize(
    ("scenario", "state"),
    [
        ("accepted", "accepted"),
        ("timeout_after_upload", "unknown"),
        ("envelope_rejected", "rejected"),
        ("rcof_rejected", "rejected"),
    ],
)
def test_builds_verifiable_five_folio_evidence(scenario: str, state: str) -> None:
    result = service().run(
        issued_on=date(2026, 7, 12),
        signed_at=datetime(2026, 7, 12, 12, tzinfo=timezone.utc),
        scenario=scenario,
    )

    assert result.document_count == 5
    assert result.final_state == state
    assert hashlib.sha256(result.evidence_zip).hexdigest() == result.evidence_sha256
    with ZipFile(io.BytesIO(result.evidence_zip)) as archive:
        names = set(archive.namelist())
        assert len([name for name in names if name.startswith("dte/")]) == 5
        assert {"sobres/envio-boleta.xml", "sobres/rcof.xml", "manifest.json"} <= names
        manifest = json.loads(archive.read("manifest.json"))
        for name, evidence in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == evidence["sha256"]


def test_evidence_is_reproducible() -> None:
    dry_run = service()
    first = dry_run.run(
        issued_on=date(2026, 7, 12),
        signed_at=datetime(2026, 7, 12, 12, tzinfo=timezone.utc),
    )
    second = dry_run.run(
        issued_on=date(2026, 7, 12),
        signed_at=datetime(2026, 7, 12, 12, tzinfo=timezone.utc),
    )
    assert first.evidence_sha256 == second.evidence_sha256


def test_rejects_unknown_scenario() -> None:
    with pytest.raises(ValueError, match="Escenario"):
        service().run(
            issued_on=date(2026, 7, 12),
            signed_at=datetime(2026, 7, 12, 12, tzinfo=timezone.utc),
            scenario="network_magic",
        )


def test_demo_api_exposes_readiness_and_failure_scenarios(tmp_path) -> None:
    client = TestClient(create_demo_app(database_path=tmp_path / "demo.sqlite3"))
    headers = {"Authorization": f"Bearer {DEMO_TOKEN}"}

    readiness = client.get("/v1/certification/readiness", headers=headers)
    assert readiness.status_code == 200
    assert readiness.json()["completed"] == 2
    assert readiness.json()["ready_to_download_caf"] is False

    run = client.post(
        "/v1/certification/dry-runs",
        headers=headers,
        json={"scenario": "timeout_after_upload"},
    )
    assert run.status_code == 200
    assert run.json()["document_count"] == 5
    assert run.json()["final_state"] == "unknown"
    assert run.json()["timeline"][-1]["state"] == "required"
