from datetime import date, datetime, timezone
from decimal import Decimal

from lxml import etree
import pytest

from completo_dte.application import (
    BoletaBatchCoordinator,
    IssueBoletaCommand,
    IssueBoletaService,
)
from completo_dte.domain import BoletaLine, EnvelopeAuthorization, Issuer
from completo_dte.infrastructure import FolioLedger, FolioLedgerError
from factories import make_signing_credential, make_trusted_caf


def setup_documents(tmp_path):
    ledger = FolioLedger(tmp_path / "batches.sqlite3")
    ledger.migrate()
    affected_caf = make_trusted_caf(document_type=39)
    exempt_caf = make_trusted_caf(document_type=41)
    cafs = {
        ledger.import_caf("tenant-a", affected_caf): affected_caf,
        ledger.import_caf("tenant-a", exempt_caf): exempt_caf,
    }
    credential = make_signing_credential()
    issuer = Issuer(
        rut="12345678-5",
        legal_name="RESTAURANTE SINTETICO SPA",
        business_activity="RESTAURANTES",
        activity_code=561000,
    )
    service = IssueBoletaService(
        ledger=ledger,
        resolve_caf=lambda caf_id: cafs[caf_id],
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 10, 14, tzinfo=timezone.utc),
    )
    affected = service.issue(IssueBoletaCommand(
        tenant_id="tenant-a",
        idempotency_key="sale-39",
        issuer=issuer,
        issued_on=date(2026, 7, 10),
        lines=(BoletaLine("Almuerzo", Decimal(1), Decimal(11900)),),
    ))
    exempt = service.issue(IssueBoletaCommand(
        tenant_id="tenant-a",
        idempotency_key="sale-41",
        issuer=issuer,
        issued_on=date(2026, 7, 10),
        lines=(BoletaLine("Servicio exento", Decimal(1), Decimal(5000), is_exempt=True),),
        document_type=41,
    ))
    coordinator = BoletaBatchCoordinator(
        ledger=ledger,
        credential=credential,
        authorization=EnvelopeAuthorization(date(2026, 7, 1), 0),
        sender_rut="12345678-5",
        clock=lambda: datetime(2026, 7, 10, 15, tzinfo=timezone.utc),
    )
    return ledger, coordinator, affected, exempt


def test_prepares_one_mixed_dispatch_and_one_daily_summary(tmp_path) -> None:
    ledger, coordinator, affected, exempt = setup_documents(tmp_path)

    dispatch = coordinator.prepare_dispatch(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
    )
    summary = coordinator.prepare_daily_summary(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
        issued_on=date(2026, 7, 10),
    )

    assert dispatch is not None and dispatch.kind == "envio_boleta"
    assert summary is not None and summary.kind == "rcof"
    dispatch_root = etree.fromstring(dispatch.signed_xml)
    assert dispatch_root.xpath("//*[local-name()='TpoDTE']/text()") == ["39", "41"]
    summary_root = etree.fromstring(summary.signed_xml)
    assert summary_root.xpath("//*[local-name()='TipoDocumento']/text()") == ["39", "41"]
    assert summary_root.xpath("//*[local-name()='MntTotal']/text()") == ["11900", "5000"]
    assert ledger.pending_envelope_documents(
        tenant_id="tenant-a", taxpayer_rut="12345678-5", relation_kind="dispatch"
    ) == ()
    assert ledger.pending_envelope_documents(
        tenant_id="tenant-a", taxpayer_rut="12345678-5", relation_kind="consumption"
    ) == ()
    assert coordinator.prepare_dispatch(
        tenant_id="tenant-a", taxpayer_rut="12345678-5"
    ) is None
    assert coordinator.prepare_daily_summary(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
        issued_on=date(2026, 7, 10),
    ) is None
    assert {affected.document_type, exempt.document_type} == {39, 41}


def test_document_cannot_be_claimed_by_two_dispatch_envelopes(tmp_path) -> None:
    ledger, _coordinator, affected, _exempt = setup_documents(tmp_path)
    first = ledger.persist_envelope_with_documents(
        tenant_id="tenant-a",
        taxpayer_rut="12345678-5",
        kind="envio_boleta",
        document_id="SetOne",
        signed_xml=b"<signed-one/>",
        document_record_ids=(affected.id,),
    )
    assert first.document_id == "SetOne"
    with pytest.raises(FolioLedgerError, match="ya pertenece"):
        ledger.persist_envelope_with_documents(
            tenant_id="tenant-a",
            taxpayer_rut="12345678-5",
            kind="envio_boleta",
            document_id="SetTwo",
            signed_xml=b"<signed-two/>",
            document_record_ids=(affected.id,),
        )
