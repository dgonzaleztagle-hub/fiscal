"""Frontera HTTP para emitir y recuperar boletas firmadas."""

from fastapi import FastAPI

from completo_dte.application import (
    InvoiceDeliveryService,
    IssueBoletaService,
    IssueCorrectionService,
    IssueDispatchService,
    IssueInvoiceService,
    RcvReconciliationService,
    ReceivedDecisionService,
    CertificationDryRunService,
)
from completo_dte.domain import (
    ReceivedDocumentValidator,
)
from completo_dte.infrastructure import (
    FolioLedger,
    RcvRepository,
)

from .correction_routes import register_correction_routes
from .certification_routes import register_certification_routes
from .document_routes import register_document_routes
from .operational_routes import register_operational_routes
from .portal_routes import register_public_portal_routes
from .rcv_routes import register_rcv_routes
from .received_routes import register_received_routes
from .report_routes import register_report_routes
from .payment_routes import register_payment_routes
from .commercial_routes import register_commercial_routes
from .treasury_routes import register_treasury_routes
from .inventory_routes import register_inventory_routes
from .recurring_routes import register_recurring_routes
from .collection_routes import register_collection_routes
from .security import build_authenticator


def create_app(
    *,
    issue_service: IssueBoletaService,
    ledger: FolioLedger,
    api_keys: dict[str, str],
    resolve_receipt_config=None,
    issue_invoice_service: IssueInvoiceService | None = None,
    invoice_delivery_service: InvoiceDeliveryService | None = None,
    issue_correction_service: IssueCorrectionService | None = None,
    issue_dispatch_service: IssueDispatchService | None = None,
    received_document_validator: ReceivedDocumentValidator | None = None,
    resolve_tenant_taxpayer_rut=None,
    received_decision_service: ReceivedDecisionService | None = None,
    rcv_repository: RcvRepository | None = None,
    rcv_reconciliation_service: RcvReconciliationService | None = None,
    certification_dry_run_service: CertificationDryRunService | None = None,
) -> FastAPI:
    """Crea una app inyectable; no lee secretos ni abre bases al importar."""
    authenticate = build_authenticator(api_keys)

    app = FastAPI(
        title="Completo DTE Engine",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )
    register_report_routes(
        app=app,
        ledger=ledger,
        authenticate=authenticate,
        rcv_repository=rcv_repository,
    )
    register_payment_routes(app=app, ledger=ledger, authenticate=authenticate)
    register_commercial_routes(app=app, ledger=ledger, authenticate=authenticate)
    register_treasury_routes(app=app, ledger=ledger, authenticate=authenticate)
    register_inventory_routes(app=app, ledger=ledger, authenticate=authenticate)
    register_recurring_routes(app=app, ledger=ledger, authenticate=authenticate)
    register_collection_routes(app=app, ledger=ledger, authenticate=authenticate)
    register_rcv_routes(
        app=app,
        authenticate=authenticate,
        rcv_repository=rcv_repository,
        rcv_reconciliation_service=rcv_reconciliation_service,
    )
    register_received_routes(
        app=app,
        ledger=ledger,
        authenticate=authenticate,
        received_document_validator=received_document_validator,
        resolve_tenant_taxpayer_rut=resolve_tenant_taxpayer_rut,
        received_decision_service=received_decision_service,
    )
    register_operational_routes(
        app=app,
        ledger=ledger,
        authenticate=authenticate,
        resolve_receipt_config=resolve_receipt_config,
        invoice_delivery_service=invoice_delivery_service,
    )
    register_public_portal_routes(
        app=app,
        ledger=ledger,
        resolve_receipt_config=resolve_receipt_config,
    )
    register_document_routes(
        app=app,
        ledger=ledger,
        authenticate=authenticate,
        issue_service=issue_service,
        issue_invoice_service=issue_invoice_service,
        issue_dispatch_service=issue_dispatch_service,
    )
    register_correction_routes(
        app=app,
        ledger=ledger,
        authenticate=authenticate,
        issue_correction_service=issue_correction_service,
    )
    register_certification_routes(
        app=app,
        authenticate=authenticate,
        dry_run_service=certification_dry_run_service,
    )

    return app
