from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor

import pytest

from completo_dte.application import IssueBoletaCommand, IssueBoletaService
from completo_dte.application.issue_boleta import command_sha256
from completo_dte.domain import (
    BoletaLine,
    Issuer,
    SignedDte,
    SchemaValidationError,
    XmlSigner,
)
from completo_dte.infrastructure import FolioLedger, FolioLedgerError, LeaseState
from factories import make_signing_credential, make_trusted_caf


def setup_issuance(tmp_path):
    ledger = FolioLedger(tmp_path / "issuance.sqlite3")
    ledger.migrate()
    caf = make_trusted_caf()
    caf_id = ledger.import_caf("restaurant-1", caf)
    credential = make_signing_credential()
    command = IssueBoletaCommand(
        tenant_id="restaurant-1",
        idempotency_key="sale-2026-0001",
        issuer=Issuer(
            rut="12345678-5",
            legal_name="RESTAURANTE SINTETICO SPA",
            business_activity="RESTAURANTES",
            activity_code=561000,
            address="CALLE UNO 123",
            commune="SANTIAGO",
        ),
        issued_on=date(2026, 7, 8),
        lines=(
            BoletaLine("Menú del día", Decimal(2), Decimal(5990)),
            BoletaLine("Café", Decimal(1), Decimal(1500)),
        ),
    )
    return ledger, caf, caf_id, credential, command


def test_issue_persists_exact_signed_xml_and_consumes_folio(tmp_path) -> None:
    ledger, caf, caf_id, credential, command = setup_issuance(tmp_path)
    service = IssueBoletaService(
        ledger=ledger,
        resolve_caf=lambda requested: caf if requested == caf_id else None,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 8, 15, 30, tzinfo=timezone.utc),
    )
    document = service.issue(command)

    assert document.folio == 1
    assert document.document_id == "F1T39"
    assert XmlSigner().verify(
        SignedDte(xml=document.signed_xml, document_id=document.document_id)
    )
    lease = ledger.reserve(
        tenant_id=command.tenant_id,
        taxpayer_rut=command.issuer.rut,
        document_type=39,
        idempotency_key=command.idempotency_key,
        request_sha256=command_sha256(command),
    )
    assert lease.status == LeaseState.CONSUMED
    assert [event["event_type"] for event in ledger.events(lease.id)] == [
        "reserved",
        "consumed",
    ]


def test_retry_after_response_loss_returns_identical_bytes_without_resigning(tmp_path) -> None:
    ledger, caf, caf_id, credential, command = setup_issuance(tmp_path)
    calls = 0

    def clock():
        nonlocal calls
        calls += 1
        return datetime(2026, 7, 8, 15, 30, tzinfo=timezone.utc) + timedelta(hours=calls)

    service = IssueBoletaService(
        ledger=ledger,
        resolve_caf=lambda _requested: caf,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=clock,
    )
    first = service.issue(command)
    retry = service.issue(command)

    assert retry == first
    assert retry.signed_xml == first.signed_xml
    assert calls == 1


def test_same_idempotency_key_rejects_changed_sale_payload(tmp_path) -> None:
    ledger, caf, _caf_id, credential, command = setup_issuance(tmp_path)
    service = IssueBoletaService(
        ledger=ledger,
        resolve_caf=lambda _requested: caf,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 8, 15, 30, tzinfo=timezone.utc),
    )
    service.issue(command)
    changed = IssueBoletaCommand(
        **{
            **command.__dict__,
            "lines": (BoletaLine("Otra venta", Decimal(1), Decimal(999_999)),),
        }
    )
    with pytest.raises(FolioLedgerError, match="payload diferente"):
        service.issue(changed)


def test_retry_recovers_reserved_folio_after_failure_before_persistence(tmp_path) -> None:
    ledger, caf, caf_id, credential, command = setup_issuance(tmp_path)
    failing = IssueBoletaService(
        ledger=ledger,
        resolve_caf=lambda _requested: (_ for _ in ()).throw(RuntimeError("vault unavailable")),
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
    )
    with pytest.raises(RuntimeError, match="vault unavailable"):
        failing.issue(command)

    recovered = IssueBoletaService(
        ledger=ledger,
        resolve_caf=lambda _requested: caf,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 8, 15, 30, tzinfo=timezone.utc),
    ).issue(command)
    assert recovered.folio == 1


def test_document_insert_and_folio_consumption_roll_back_together(tmp_path) -> None:
    ledger, _caf, _caf_id, _credential, command = setup_issuance(tmp_path)
    lease = ledger.reserve(
        tenant_id=command.tenant_id,
        taxpayer_rut=command.issuer.rut,
        document_type=39,
        idempotency_key=command.idempotency_key,
        request_sha256=command_sha256(command),
    )
    with pytest.raises(FolioLedgerError, match="ID fiscal"):
        ledger.persist_signed_document(
            lease.id,
            document_id="WRONG",
            signed_xml=b"<signed/>",
        )

    assert ledger.document_by_lease(lease.id) is None
    same = ledger.reserve(
        tenant_id=command.tenant_id,
        taxpayer_rut=command.issuer.rut,
        document_type=39,
        idempotency_key=command.idempotency_key,
        request_sha256=command_sha256(command),
    )
    assert same.status == LeaseState.RESERVED


def test_concurrent_same_sale_returns_one_persisted_document(tmp_path) -> None:
    ledger, caf, _caf_id, credential, command = setup_issuance(tmp_path)
    service = IssueBoletaService(
        ledger=ledger,
        resolve_caf=lambda _requested: caf,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 8, 15, 30, tzinfo=timezone.utc),
    )
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(lambda _index: service.issue(command), range(16)))

    assert len({result.id for result in results}) == 1
    assert len({result.signed_xml for result in results}) == 1
    assert {result.folio for result in results} == {1}


def test_schema_failure_does_not_persist_or_consume_folio(tmp_path) -> None:
    ledger, caf, _caf_id, credential, command = setup_issuance(tmp_path)

    def reject(_document):
        raise SchemaValidationError("invalid fixture")

    service = IssueBoletaService(
        ledger=ledger,
        resolve_caf=lambda _requested: caf,
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=reject,
        clock=lambda: datetime(2026, 7, 8, 15, 30, tzinfo=timezone.utc),
    )
    with pytest.raises(SchemaValidationError):
        service.issue(command)

    lease = ledger.reserve(
        tenant_id=command.tenant_id,
        taxpayer_rut=command.issuer.rut,
        document_type=39,
        idempotency_key=command.idempotency_key,
        request_sha256=command_sha256(command),
    )
    assert lease.status == LeaseState.RESERVED
    assert ledger.document_by_lease(lease.id) is None
