from datetime import datetime, timezone
from importlib.resources import files

from fastapi.testclient import TestClient

from completo_dte.api import create_app
from completo_dte.application import (
    InvoiceDeliveryService,
    IssueBoletaService,
    IssueCorrectionService,
    IssueDispatchService,
    DecisionRemoteResult,
    ReceivedDecisionService,
    RcvReconciliationService,
    IssueInvoiceService,
)
from completo_dte.domain import EnvelopeAuthorization, ReceivedDocumentValidator
from completo_dte.infrastructure import FolioLedger, RcvRepository
from completo_dte.presentation import ReceiptConfig
from factories import make_signing_credential, make_trusted_caf


TOKEN_A = "local-test-token-a-with-sufficient-entropy"
TOKEN_B = "local-test-token-b-with-sufficient-entropy"


class ConfirmingDecisionGateway:
    def submit(self, _payload):
        return DecisionRemoteResult(True, "0", "Registrado en simulador")

    def query(self, _payload):
        return DecisionRemoteResult(True, "0", "Conciliado en simulador")


def make_client(tmp_path) -> TestClient:
    database = tmp_path / "api.sqlite3"
    ledger = FolioLedger(database)
    ledger.migrate()
    caf = make_trusted_caf()
    caf_id = ledger.import_caf("tenant-a", caf)
    exempt_caf = make_trusted_caf(document_type=41)
    exempt_caf_id = ledger.import_caf("tenant-a", exempt_caf)
    invoice_caf = make_trusted_caf(document_type=33)
    invoice_caf_id = ledger.import_caf("tenant-a", invoice_caf)
    exempt_invoice_caf = make_trusted_caf(document_type=34)
    exempt_invoice_caf_id = ledger.import_caf("tenant-a", exempt_invoice_caf)
    credit_caf = make_trusted_caf(document_type=61)
    credit_caf_id = ledger.import_caf("tenant-a", credit_caf)
    debit_caf = make_trusted_caf(document_type=56)
    debit_caf_id = ledger.import_caf("tenant-a", debit_caf)
    dispatch_caf = make_trusted_caf(document_type=52)
    dispatch_caf_id = ledger.import_caf("tenant-a", dispatch_caf)
    cafs = {
        caf_id: caf,
        exempt_caf_id: exempt_caf,
        invoice_caf_id: invoice_caf,
        exempt_invoice_caf_id: exempt_invoice_caf,
        credit_caf_id: credit_caf,
        debit_caf_id: debit_caf,
        dispatch_caf_id: dispatch_caf,
    }
    credential = make_signing_credential()
    service = IssueBoletaService(
        ledger=ledger,
        resolve_caf=lambda requested: cafs.get(requested),
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 8, 15, 30, tzinfo=timezone.utc),
    )
    invoice_service = IssueInvoiceService(
        ledger=ledger,
        resolve_caf=lambda requested: cafs.get(requested),
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 8, 15, 30, tzinfo=timezone.utc),
    )
    delivery_service = InvoiceDeliveryService(
        ledger=ledger,
        credential=credential,
        authorization=EnvelopeAuthorization(
            datetime(2026, 7, 1, tzinfo=timezone.utc).date(),
            0,
        ),
        sender_rut="12345678-5",
        receipt_config=ReceiptConfig(
            verification_url="https://documentos.completo.cl",
            resolution_number=80,
            resolution_year=2014,
        ),
        clock=lambda: datetime(2026, 7, 8, 15, 30, tzinfo=timezone.utc),
    )
    correction_service = IssueCorrectionService(
        ledger=ledger,
        resolve_caf=lambda requested: cafs.get(requested),
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 11, 15, 30, tzinfo=timezone.utc),
    )
    dispatch_service = IssueDispatchService(
        ledger=ledger,
        resolve_caf=lambda requested: cafs.get(requested),
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 8, 15, 30, tzinfo=timezone.utc),
    )
    rcv_repository = RcvRepository(database)
    app = create_app(
        issue_service=service,
        ledger=ledger,
        api_keys={TOKEN_A: "tenant-a", TOKEN_B: "tenant-b"},
        issue_invoice_service=invoice_service,
        invoice_delivery_service=delivery_service,
        issue_correction_service=correction_service,
        issue_dispatch_service=dispatch_service,
        received_document_validator=ReceivedDocumentValidator(
            files("completo_dte").joinpath(
                "resources", "sii", "schema_dte_v10", "DTE_v10.xsd"
            )
        ),
        resolve_tenant_taxpayer_rut=lambda tenant: (
            "11111111-1" if tenant == "tenant-a" else "22222222-2"
        ),
        received_decision_service=ReceivedDecisionService(
            ledger=ledger, gateway=ConfirmingDecisionGateway()
        ),
        rcv_repository=rcv_repository,
        rcv_reconciliation_service=RcvReconciliationService(
            ledger=ledger, repository=rcv_repository
        ),
        resolve_receipt_config=lambda _tenant, _rut: ReceiptConfig(
            verification_url="https://boletas.completo.cl",
            resolution_number=80,
            resolution_year=2014,
        ),
    )
    return TestClient(app)


def payload() -> dict:
    return {
        "document_type": 39,
        "issued_on": "2026-07-08",
        "issuer": {
            "rut": "12345678-5",
            "legal_name": "RESTAURANTE SINTETICO SPA",
            "business_activity": "RESTAURANTES",
            "activity_code": 561000,
            "address": "CALLE UNO 123",
            "commune": "SANTIAGO",
        },
        "lines": [
            {
                "name": "Menú del día",
                "quantity": "2",
                "unit_price_gross": "5990",
                "discount_gross": "0",
            }
        ],
    }


def auth(token: str = TOKEN_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_commercial_inventory_and_treasury_apis_are_tenant_scoped(tmp_path) -> None:
    client = make_client(tmp_path)
    commercial = client.post("/v1/commercial-documents", headers={**auth(),"Idempotency-Key":"quote-api-1"}, json={
        "kind":"quote","branch_id":"main","counterparty_ref":"client-1","counterparty_name":"Cliente Uno",
        "issued_on":"2026-07-13","valid_until":"2026-07-30","currency":"CLP","notes":"",
        "lines":[{"description":"Servicio","quantity":"1","unit_price":"100000","discount_percent":"0"}],
    })
    assert commercial.status_code == 201
    assert client.get("/v1/commercial-documents",headers=auth(TOKEN_B)).json() == []
    product = client.post("/v1/inventory/products",headers=auth(),json={"sku":"SKU-1","name":"Producto","unit":"un"})
    assert product.status_code == 201
    movement = client.post("/v1/inventory/movements",headers={**auth(),"Idempotency-Key":"movement-api-1"},json={
        "product_id":product.json()["id"],"branch_id":"main","movement_type":"purchase","quantity":"5",
        "source_ref":"OC-1","reason":"Recepción"})
    assert movement.status_code == 201
    balance=client.get(f"/v1/inventory/products/{product.json()['id']}/branches/main/balance",headers=auth()).json()
    assert balance["quantity"] == "5"
    obligation=client.post("/v1/obligations",headers=auth(),json={"direction":"receivable","counterparty_ref":"client-1","counterparty_name":"Cliente Uno","source_ref":"F33-9","branch_id":"main","amount":100000,"due_on":"2026-07-30"})
    assert obligation.status_code == 201
    paid=client.post(f"/v1/obligations/{obligation.json()['id']}/payments",headers={**auth(),"Idempotency-Key":"payment-api-1"},json={"amount":25000,"paid_on":"2026-07-15","method":"transfer","evidence_ref":"bank-1"})
    assert paid.status_code == 201 and paid.json()["outstanding"] == 75000
    approval=client.post("/v1/approvals",headers=auth(),json={"operation_type":"purchase_order","operation_ref":"OC-99","amount":900000,"required_role":"owner"})
    assert approval.status_code == 201
    assert client.get("/v1/approvals?status=pending",headers=auth()).json()[0]["operation_ref"] == "OC-99"
    decision=client.post(f"/v1/approvals/{approval.json()['id']}/decision",headers=auth(),json={"decision":"approved","reason":"Autorizada"})
    assert decision.status_code == 200 and decision.json()["status"] == "approved"


def test_health_does_not_require_credentials(tmp_path) -> None:
    response = make_client(tmp_path).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_emission_requires_bearer_and_idempotency_key(tmp_path) -> None:
    client = make_client(tmp_path)
    assert client.post("/v1/fiscal-documents", json=payload()).status_code == 401
    response = client.post("/v1/fiscal-documents", json=payload(), headers=auth())
    assert response.status_code == 400
    assert response.json()["detail"] == "Idempotency-Key es obligatorio"


def test_issue_retry_metadata_and_xml_round_trip(tmp_path) -> None:
    client = make_client(tmp_path)
    headers = {**auth(), "Idempotency-Key": "sale-http-1"}
    first = client.post("/v1/fiscal-documents", json=payload(), headers=headers)
    retry = client.post("/v1/fiscal-documents", json=payload(), headers=headers)

    assert first.status_code == 201
    assert retry.status_code == 201
    assert retry.json() == first.json()
    body = first.json()
    assert body["document_id"] == "F1T39"
    assert body["status"] == "signed"
    assert body["counterparty_name"] == "SIN INFORMACION"
    assert body["issued_on"] == "2026-07-08"
    assert body["total"] == 11980

    metadata = client.get(f"/v1/fiscal-documents/{body['id']}", headers=auth())
    xml = client.get(f"/v1/fiscal-documents/{body['id']}/xml", headers=auth())
    assert metadata.json() == body
    assert xml.status_code == 200
    assert xml.headers["content-type"].startswith("application/xml")
    assert xml.headers["x-content-sha256"] == body["xml_sha256"]
    assert xml.content.startswith(b'<?xml version="1.0" encoding="ISO-8859-1"?>')

    listed = client.get("/v1/fiscal-documents", headers=auth())
    events = client.get(
        f"/v1/fiscal-documents/{body['id']}/events",
        headers=auth(),
    )
    pdf = client.get(f"/v1/fiscal-documents/{body['id']}/pdf", headers=auth())
    assert listed.json() == [body]
    assert [event["event_type"] for event in events.json()] == ["reserved", "consumed"]
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF-")

    envelopes = client.get("/v1/fiscal-envelopes", headers=auth())
    alerts = client.get("/v1/operational-alerts", headers=auth())
    assert envelopes.status_code == 200
    assert envelopes.json() == []
    assert alerts.status_code == 200
    assert any(alert["code"] == "rcof_pending" for alert in alerts.json())


def test_other_tenant_cannot_discover_metadata_or_xml(tmp_path) -> None:
    client = make_client(tmp_path)
    created = client.post(
        "/v1/fiscal-documents",
        json=payload(),
        headers={**auth(), "Idempotency-Key": "sale-secret"},
    ).json()
    for suffix in ("", "/xml"):
        response = client.get(
            f"/v1/fiscal-documents/{created['id']}{suffix}",
            headers=auth(TOKEN_B),
        )
        assert response.status_code == 404


def test_public_receipt_uses_opaque_url_without_exposing_xml(tmp_path) -> None:
    client = make_client(tmp_path)
    created = client.post(
        "/v1/fiscal-documents",
        json=payload(),
        headers={**auth(), "Idempotency-Key": "sale-public"},
    ).json()
    page = client.get(created["public_url"])
    pdf = client.get(created["public_url"] + "/pdf")

    assert page.status_code == 200
    assert "Boleta electrónica" in page.text
    assert "<DTE" not in page.text
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF-")
    assert client.get("/public/v1/boletas/" + "0" * 32).status_code == 404


def test_tenant_without_caf_gets_safe_conflict(tmp_path) -> None:
    client = make_client(tmp_path)
    response = client.post(
        "/v1/fiscal-documents",
        json=payload(),
        headers={**auth(TOKEN_B), "Idempotency-Key": "sale-no-caf"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "No quedan folios disponibles"


def test_rejects_unknown_fields_and_unsupported_document_type(tmp_path) -> None:
    client = make_client(tmp_path)
    malformed = payload()
    malformed["surprise"] = "ignored?"
    response = client.post(
        "/v1/fiscal-documents",
        json=malformed,
        headers={**auth(), "Idempotency-Key": "sale-malformed"},
    )
    assert response.status_code == 422

    unsupported = payload()
    unsupported["document_type"] = 56
    response = client.post(
        "/v1/fiscal-documents",
        json=unsupported,
        headers={**auth(), "Idempotency-Key": "sale-52"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Este tipo documental todavía no tiene emisor implementado"


def test_issues_exempt_boleta_41_through_same_idempotent_endpoint(tmp_path) -> None:
    client = make_client(tmp_path)
    request = payload()
    request["document_type"] = 41
    request["lines"][0]["is_exempt"] = True
    response = client.post(
        "/v1/fiscal-documents",
        json=request,
        headers={**auth(), "Idempotency-Key": "sale-exempt-41"},
    )

    assert response.status_code == 201
    assert response.json()["document_type"] == 41
    assert response.json()["document_id"] == "F1T41"
    xml = client.get(response.json()["xml_url"], headers=auth())
    assert b"<TipoDTE>41</TipoDTE>" in xml.content
    assert b"<MntExe>11980</MntExe>" in xml.content
    assert b"<IVA>" not in xml.content


def test_same_http_idempotency_key_with_changed_payload_returns_conflict(tmp_path) -> None:
    client = make_client(tmp_path)
    headers = {**auth(), "Idempotency-Key": "sale-conflict"}
    assert client.post("/v1/fiscal-documents", json=payload(), headers=headers).status_code == 201
    changed = payload()
    changed["lines"][0]["unit_price_gross"] = "999999"
    response = client.post("/v1/fiscal-documents", json=changed, headers=headers)
    assert response.status_code == 409
    assert "payload diferente" in response.json()["detail"]


def test_capabilities_exposes_complete_v1_contract(tmp_path) -> None:
    client = make_client(tmp_path)
    response = client.get("/v1/capabilities", headers=auth())
    assert response.status_code == 200
    types = response.json()["document_types"]
    assert {item["code"] for item in types} == {33, 34, 39, 41, 52, 56, 61}
    assert next(item for item in types if item["code"] == 39)["builder"] == "implemented"
    assert next(item for item in types if item["code"] == 41)["builder"] == "implemented"
    assert next(item for item in types if item["code"] == 33)["builder"] == "implemented"
    assert next(item for item in types if item["code"] == 34)["builder"] == "implemented"


def test_validates_canonical_invoice_draft_without_issuing_folio(tmp_path) -> None:
    client = make_client(tmp_path)
    response = client.post(
        "/v1/fiscal-document-drafts/validate",
        headers=auth(),
        json={
            "branch_id": "casa-matriz",
            "issuer_profile_id": "issuer-demo",
            "document_type": 33,
            "issued_on": "2026-07-09",
            "receiver": {
                "rut": "76192083-9",
                "legal_name": "CLIENTE SINTETICO SPA",
                "business_activity": "SERVICIOS",
            },
            "lines": [
                {
                    "name": "Servicio mensual",
                    "quantity": "1",
                    "unit_price": "10000",
                    "tax_category": "affected",
                    "price_mode": "net",
                }
            ],
            "payment_terms": 1,
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "document_type": 33,
        "document_name": "Factura electrónica",
        "line_count": 1,
        "receiver_required": True,
        "builder_status": "implemented",
    }


def test_issues_factura_33_through_general_fiscal_endpoint(tmp_path) -> None:
    client = make_client(tmp_path)
    request = {
        "document_type": 33,
        "issued_on": "2026-07-10",
        "issuer": payload()["issuer"],
        "receiver": {
            "rut": "11111111-1",
            "legal_name": "CLIENTE SINTETICO SPA",
            "business_activity": "SERVICIOS EMPRESARIALES",
            "address": "CALLE DOS 200",
            "commune": "PROVIDENCIA",
            "email": "facturas@example.test",
        },
        "lines": [
            {
                "name": "Servicio mensual",
                "quantity": "1",
                "unit_price": "10000",
                "tax_category": "affected",
                "price_mode": "net",
            }
        ],
        "payment_terms": 2,
        "due_on": "2026-08-10",
    }
    response = client.post(
        "/v1/fiscal-documents",
        json=request,
        headers={**auth(), "Idempotency-Key": "invoice-http-33"},
    )

    assert response.status_code == 201
    assert response.json()["document_type"] == 33
    assert response.json()["document_id"] == "F1T33"
    xml = client.get(response.json()["xml_url"], headers=auth())
    assert b"<MntNeto>10000</MntNeto>" in xml.content
    assert b"<IVA>1900</IVA>" in xml.content
    assert b"<MntTotal>11900</MntTotal>" in xml.content

    delivery = client.post(
        f"/v1/fiscal-documents/{response.json()['id']}/deliveries",
        json={},
        headers=auth(),
    )
    assert delivery.status_code == 201
    assert delivery.json()["recipient_email"] == "facturas@example.test"
    assert delivery.json()["status"] == "queued"
    fetched = client.get(
        f"/v1/fiscal-deliveries/{delivery.json()['id']}",
        headers=auth(),
    )
    assert fetched.status_code == 200
    assert fetched.json()["exchange_xml_sha256"] == delivery.json()["exchange_xml_sha256"]

    correction = client.post(
        f"/v1/fiscal-documents/{response.json()['id']}/corrections",
        headers={**auth(), "Idempotency-Key": "credit-http-61"},
        json={
            "document_type": 61,
            "issued_on": "2026-07-11",
            "issuer": request["issuer"],
            "reason": "Diferencia en precio",
            "lines": [
                {
                    "name": "Diferencia servicio",
                    "quantity": "1",
                    "unit_price": "1000",
                    "tax_category": "affected",
                    "price_mode": "net",
                }
            ],
        },
    )
    assert correction.status_code == 201
    assert correction.json()["document_type"] == 61
    assert correction.json()["document_id"] == "F1T61"
    correction_pdf = client.get(
        f"/v1/fiscal-documents/{correction.json()['id']}/pdf",
        headers=auth(),
    )
    assert correction_pdf.status_code == 200
    assert correction_pdf.content.startswith(b"%PDF-")

    second_invoice = client.post(
        "/v1/fiscal-documents",
        json=request,
        headers={**auth(), "Idempotency-Key": "invoice-for-annulment"},
    )
    assert second_invoice.status_code == 201
    annulment = client.post(
        f"/v1/fiscal-documents/{second_invoice.json()['id']}/annulment",
        json={"issued_on": "2026-07-11"},
        headers={**auth(), "Idempotency-Key": "annulment-http-61"},
    )
    assert annulment.status_code == 201
    assert annulment.json()["document_type"] == 61
    annulment_xml = client.get(annulment.json()["xml_url"], headers=auth())
    assert b"<CodRef>1</CodRef>" in annulment_xml.content

    text_invoice = client.post(
        "/v1/fiscal-documents",
        json=request,
        headers={**auth(), "Idempotency-Key": "invoice-for-text-fix"},
    )
    assert text_invoice.status_code == 201
    text_fix = client.post(
        f"/v1/fiscal-documents/{text_invoice.json()['id']}/corrections/text",
        json={
            "issued_on": "2026-07-11",
            "business_activity": "GIRO CORREGIDO",
            "address": "DIRECCION CORREGIDA 123",
            "commune": "SANTIAGO",
        },
        headers={**auth(), "Idempotency-Key": "text-fix-http-61"},
    )
    assert text_fix.status_code == 201
    text_xml = client.get(text_fix.json()["xml_url"], headers=auth())
    assert b"<CodRef>2</CodRef>" in text_xml.content
    assert b"<MntTotal>0</MntTotal>" in text_xml.content


def test_issues_guide_52_sale_and_internal_transfer(tmp_path) -> None:
    client = make_client(tmp_path)
    sale = {
        "document_type": 52,
        "issued_on": "2026-07-10",
        "issuer": payload()["issuer"],
        "receiver": {
            "rut": "11111111-1",
            "legal_name": "CLIENTE SINTETICO SPA",
            "business_activity": "COMERCIO",
            "address": "BODEGA DOS 200",
            "commune": "PROVIDENCIA",
        },
        "dispatch_reason": 1,
        "dispatch_account": 2,
        "transport": {
            "vehicle_plate": "ABCD12",
            "destination_address": "BODEGA DOS 200",
            "destination_commune": "PROVIDENCIA",
        },
        "lines": [
            {
                "name": "Equipo",
                "quantity": "2",
                "unit_price": "10000",
                "tax_category": "affected",
                "price_mode": "net",
            }
        ],
    }
    response = client.post(
        "/v1/fiscal-documents",
        json=sale,
        headers={**auth(), "Idempotency-Key": "guide-sale-http-52"},
    )
    assert response.status_code == 201
    assert response.json()["document_id"] == "F1T52"
    xml = client.get(response.json()["xml_url"], headers=auth())
    assert b"<TipoDespacho>2</TipoDespacho>" in xml.content
    assert b"<IndTraslado>1</IndTraslado>" in xml.content
    assert b"<MntTotal>23800</MntTotal>" in xml.content
    pdf = client.get(f"/v1/fiscal-documents/{response.json()['id']}/pdf", headers=auth())
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF-")

    internal = {
        **sale,
        "receiver": {
            "rut": payload()["issuer"]["rut"],
            "legal_name": payload()["issuer"]["legal_name"],
            "business_activity": payload()["issuer"]["business_activity"],
            "address": payload()["issuer"]["address"],
            "commune": payload()["issuer"]["commune"],
        },
        "dispatch_reason": 5,
        "dispatch_account": None,
        "lines": [
            {
                "name": "Equipo",
                "quantity": "2",
                "unit_price": "0",
                "tax_category": "non_billable",
                "price_mode": "net",
            }
        ],
    }
    response = client.post(
        "/v1/fiscal-documents",
        json=internal,
        headers={**auth(), "Idempotency-Key": "guide-internal-http-52"},
    )
    assert response.status_code == 201
    xml = client.get(response.json()["xml_url"], headers=auth())
    assert b"<IndTraslado>5</IndTraslado>" in xml.content
    assert b"<TipoDespacho>" not in xml.content
    assert b"<PrcItem>" not in xml.content
    assert b"<MntTotal>0</MntTotal>" in xml.content


def test_imports_and_lists_received_signed_xml_with_tenant_isolation(tmp_path) -> None:
    from test_official_invoice_schema import signed_invoice

    client = make_client(tmp_path)
    signed, _credential, _timestamp = signed_invoice()
    imported = client.post(
        "/v1/received-documents/import?source=upload",
        content=signed.xml,
        headers={**auth(), "Content-Type": "application/xml"},
    )
    retry = client.post(
        "/v1/received-documents/import?source=email",
        content=signed.xml,
        headers={**auth(), "Content-Type": "application/xml"},
    )

    assert imported.status_code == 201
    assert retry.json() == imported.json()
    assert imported.json()["issuer_rut"] == "12345678-5"
    assert imported.json()["total"] == 21420
    assert client.get("/v1/received-documents", headers=auth()).json() == [
        imported.json()
    ]
    assert client.get("/v1/received-documents", headers=auth(TOKEN_B)).json() == []
    decision = client.post(
        f"/v1/received-documents/{imported.json()['id']}/decision",
        json={"decision": "claim_content", "reason": "Monto no corresponde"},
        headers=auth(),
    )
    assert decision.status_code == 201
    assert decision.json()["status"] == "confirmed"
    assert decision.json()["remote_code"] == "0"
    assert client.post(
        f"/v1/received-documents/{imported.json()['id']}/decision",
        json={"decision": "accept_content"},
        headers=auth(),
    ).status_code == 409
    classification = client.post(
        f"/v1/received-documents/{imported.json()['id']}/classification",
        json={
            "provider_id": "provider-demo",
            "destination": "expense",
            "category_code": "supplies",
            "notes": "Compra de operación",
        },
        headers={**auth(), "X-Actor-Id": "user-demo"},
    )
    assert classification.status_code == 201
    assert classification.json()["version"] == 1
    assert classification.json()["classified_by"] == "user-demo"
    latest = client.get(
        f"/v1/received-documents/{imported.json()['id']}/classification",
        headers=auth(),
    )
    assert latest.json() == classification.json()
    allocations = client.post(
        f"/v1/received-classifications/{classification.json()['id']}/line-allocations",
        json={
            "allocations": [
                {
                    "line_number": 1,
                    "destination": "expense",
                    "control_plane_ref": "expense-item-demo",
                }
            ]
        },
        headers=auth(),
    )
    assert allocations.status_code == 201
    assert allocations.json()[0]["line_number"] == 1
    rcv = client.post(
        "/v1/rcv/purchases/snapshots",
        json={
            "year": 2026,
            "month": 7,
            "source": "synthetic",
            "entries": [
                {
                    "issuer_rut": imported.json()["issuer_rut"],
                    "document_type": imported.json()["document_type"],
                    "folio": imported.json()["folio"],
                    "issued_on": imported.json()["issued_on"],
                    "exempt_amount": 0,
                    "net_amount": 18000,
                    "vat_amount": 3420,
                    "total_amount": imported.json()["total"],
                    "status": "registered",
                }
            ],
        },
        headers=auth(),
    )
    assert rcv.status_code == 201
    reconciliation = client.get(
        "/v1/rcv/purchases/2026/7/reconciliation", headers=auth()
    )
    assert reconciliation.status_code == 200
    assert reconciliation.json()[0]["kind"] == "match"
    report = client.get("/v1/reports/monthly/2026/7.csv", headers=auth())
    assert report.status_code == 200
    assert report.content.startswith(b"\xef\xbb\xbf")
    assert len(report.headers["x-content-sha256"]) == 64
    assert "completo-fiscal-2026-07.csv" in report.headers["content-disposition"]
    xlsx = client.get("/v1/reports/monthly/2026/7.xlsx", headers=auth())
    assert xlsx.status_code == 200
    assert xlsx.content.startswith(b"PK")
    assert len(xlsx.headers["x-content-sha256"]) == 64
    pdf_report = client.get("/v1/reports/monthly/2026/7.pdf", headers=auth())
    assert pdf_report.status_code == 200
    assert pdf_report.content.startswith(b"%PDF-")
    package = client.get(
        "/v1/reports/monthly/2026/7/accountant-package.zip", headers=auth()
    )
    assert package.status_code == 200
    assert package.content.startswith(b"PK")
    assert len(package.headers["x-content-sha256"]) == 64


def test_monthly_close_is_explainable_and_validates_adjustments(tmp_path) -> None:
    client = make_client(tmp_path)
    response = client.post(
        "/v1/reports/monthly/2026/7/close",
        headers=auth(),
        json={
            "prior_vat_credit": 1000,
            "ppm_rate_basis_points": 100,
            "sii_proposal": {"sales_vat": 0},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "2026-07"
    assert body["formula_version"] == "plus-baseline-2026-07-v1"
    assert len(body["source_hash"]) == 64
    assert len(body["calculation_hash"]) == 64
    assert body["version"] == 1
    assert body["snapshot_id"]
    assert body["notice"].startswith("Propuesta informativa")
    assert {line["state"] for line in body["lines"]} <= {
        "match",
        "different",
        "not_compared",
    }

    negative = client.post(
        "/v1/reports/monthly/2026/7/close",
        headers=auth(),
        json={"prior_vat_credit": -1},
    )
    unknown = client.post(
        "/v1/reports/monthly/2026/7/close",
        headers=auth(),
        json={"invented_tax": 1},
    )
    assert negative.status_code == 422
    assert unknown.status_code == 422

    retry = client.post(
        "/v1/reports/monthly/2026/7/close",
        headers=auth(),
        json={
            "prior_vat_credit": 1000,
            "ppm_rate_basis_points": 100,
            "sii_proposal": {"sales_vat": 0},
        },
    )
    assert retry.json()["snapshot_id"] == body["snapshot_id"]
    snapshots = client.get(
        "/v1/reports/monthly/2026/7/close/snapshots", headers=auth()
    )
    assert snapshots.status_code == 200
    assert len(snapshots.json()) == 1

    opened = client.post(
        f"/v1/reports/monthly/close/snapshots/{body['snapshot_id']}/reviews",
        headers=auth(),
        json={"actor_ref": "user-demo", "action": "opened"},
    )
    cross_tenant = client.post(
        f"/v1/reports/monthly/close/snapshots/{body['snapshot_id']}/reviews",
        headers=auth(TOKEN_B),
        json={"actor_ref": "intruder", "action": "opened"},
    )
    assert opened.status_code == 200
    assert opened.json()["actor_ref"] == "authenticated-tenant:tenant-a"
    assert cross_tenant.status_code == 422

    dossier = client.get(
        "/v1/reports/monthly/2026/7/dossier", headers=auth()
    )
    assert dossier.status_code == 200
    dossier_body = dossier.json()
    assert dossier_body["period"] == "2026-07"
    assert len(dossier_body["evidence_hash"]) == 64
    assert {item["code"] for item in dossier_body["items"]} == {
        "documents", "rcv", "close", "bhe", "people", "payments"
    }
    assert next(
        item for item in dossier_body["items"] if item["code"] == "close"
    )["state"] == "ready"


def test_payment_import_reconciliation_and_tenant_isolation(tmp_path) -> None:
    client = make_client(tmp_path)
    payment = client.post(
        "/v1/payments/electronic",
        headers=auth(),
        json={
            "provider": "Transbank", "terminal_id": "POS-1",
            "authorization_code": "AUTH-1", "provider_reference": "TBK-1",
            "sale_ref": "sale-1", "amount": 11900,
            "occurred_at": "2026-07-12T13:00:00-04:00",
            "settlement_ref": "settle-1", "source": "provider_import",
        },
    )
    assert payment.status_code == 201
    result = client.post(
        "/v1/payments/reconciliation/2026/7",
        headers=auth(),
        json={"sales": [{"sale_ref": "sale-1", "amount": 11900,
                          "emission_model": "voucher_as_boleta"}]},
    )
    assert result.status_code == 200
    assert result.json()["ready"] is True
    bogus_dte = client.post(
        "/v1/payments/reconciliation/2026/7", headers=auth(),
        json={"sales": [{"sale_ref": "sale-1", "amount": 11900,
                         "emission_model": "always_issue",
                         "fiscal_document_ref": "DOES-NOT-EXIST"}]},
    )
    assert bogus_dte.status_code == 422
    latest = client.get("/v1/payments/reconciliation/2026/7", headers=auth())
    other = client.get("/v1/payments/reconciliation/2026/7", headers=auth(TOKEN_B))
    assert latest.json()["snapshot_id"] == result.json()["snapshot_id"]
    assert other.status_code == 404
    people = client.post(
        "/v1/integrations/people/monthly-summaries",
        headers=auth(),
        json={"period": "2026-07", "worker_count": 4,
              "taxable_payroll": 3200000, "pension_obligations": 620000,
              "single_tax": 45000, "other_withholdings": 10000,
              "source_version": "people-v7"},
    )
    assert people.status_code == 201
    assert client.get(
        "/v1/integrations/people/monthly-summaries/2026/7", headers=auth()
    ).json()["worker_count"] == 4
    dossier = client.get("/v1/reports/monthly/2026/7/dossier", headers=auth()).json()
    assert next(item for item in dossier["items"] if item["code"] == "payments")["state"] == "ready"
    assert next(item for item in dossier["items"] if item["code"] == "people")["state"] == "ready"
    recalculated = client.post(
        "/v1/reports/monthly/2026/7/close", headers=auth(), json={}
    ).json()
    lines = {line["code"]: line["amount"] for line in recalculated["lines"]}
    assert lines["single_tax"] == 45000
    assert lines["additional_withholding"] == 10000
