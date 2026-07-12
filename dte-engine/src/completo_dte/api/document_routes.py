"""Rutas de emisión, consulta y corrección de documentos tributarios."""

from collections.abc import Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import Response

from completo_dte.application import (
    IssueBoletaService,
    IssueDispatchService,
    IssueInvoiceService,
)
from completo_dte.domain import (
    BoletaError,
    DispatchError,
    DocumentType,
    FiscalDocumentDraft,
    FiscalDocumentError,
    FiscalLine,
    FiscalReference,
    InvoiceError,
    Party,
    RutError,
    SchemaValidationError,
    TedError,
)
from completo_dte.infrastructure import CafRangeExhausted, FolioLedger, FolioLedgerError

from .contracts import (
    DocumentResponse,
    DraftValidationResponse,
    FiscalDraftRequest,
    IssueRequest,
)
from .issue_mapping import IssueServiceUnavailable, issue_from_request
from .projections import _document_name, _response
from .security import ApiPrincipal


def register_document_routes(
    *,
    app: FastAPI,
    ledger: FolioLedger,
    authenticate: Callable[..., ApiPrincipal],
    issue_service: IssueBoletaService,
    issue_invoice_service: IssueInvoiceService | None,
    issue_dispatch_service: IssueDispatchService | None,
) -> None:
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "completo-dte-engine"}

    @app.get("/v1/capabilities")
    def capabilities(
        _principal: ApiPrincipal = Depends(authenticate),
    ) -> dict[str, object]:
        implemented = set(DocumentType)
        return {
            "api_version": "1.0.0",
            "document_types": [
                {
                    "code": int(document_type),
                    "name": _document_name(document_type),
                    "contract": "available",
                    "builder": (
                        "implemented" if document_type in implemented else "planned"
                    ),
                }
                for document_type in DocumentType
            ],
            "environments": ["demo", "certification", "production"],
        }

    @app.post(
        "/v1/fiscal-document-drafts/validate",
        response_model=DraftValidationResponse,
    )
    def validate_fiscal_draft(
        payload: FiscalDraftRequest,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> DraftValidationResponse:
        try:
            draft = FiscalDocumentDraft(
                tenant_id=principal.tenant_id,
                branch_id=payload.branch_id,
                issuer_profile_id=payload.issuer_profile_id,
                document_type=payload.document_type,
                issued_on=payload.issued_on,
                lines=tuple(FiscalLine(**line.model_dump()) for line in payload.lines),
                receiver=(
                    Party(**payload.receiver.model_dump()) if payload.receiver else None
                ),
                payment_method=payload.payment_method,
                payment_terms=payload.payment_terms,
                due_on=payload.due_on,
                dispatch_reason=payload.dispatch_reason,
                references=tuple(
                    FiscalReference(**reference.model_dump())
                    for reference in payload.references
                ),
                currency=payload.currency,
            )
        except (FiscalDocumentError, RutError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return DraftValidationResponse(
            valid=True,
            document_type=int(draft.document_type),
            document_name=_document_name(draft.document_type),
            line_count=len(draft.lines),
            receiver_required=draft.document_type
            not in {DocumentType.BOLETA_AFECTA, DocumentType.BOLETA_EXENTA},
            builder_status=(
                "implemented" if draft.document_type in set(DocumentType) else "planned"
            ),
        )

    @app.post(
        "/v1/fiscal-documents",
        response_model=DocumentResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def issue_document(
        payload: IssueRequest,
        request: Request,
        principal: ApiPrincipal = Depends(authenticate),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> DocumentResponse:
        if not idempotency_key or not idempotency_key.strip():
            raise HTTPException(
                status_code=400, detail="Idempotency-Key es obligatorio"
            )
        if len(idempotency_key) > 200:
            raise HTTPException(
                status_code=400, detail="Idempotency-Key excede 200 caracteres"
            )
        try:
            record = issue_from_request(
                payload=payload,
                tenant_id=principal.tenant_id,
                idempotency_key=idempotency_key,
                issue_service=issue_service,
                issue_invoice_service=issue_invoice_service,
                issue_dispatch_service=issue_dispatch_service,
            )
        except IssueServiceUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except CafRangeExhausted as exc:
            raise HTTPException(
                status_code=409, detail="No quedan folios disponibles"
            ) from exc
        except FolioLedgerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except SchemaValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail="El documento no cumple la validación tributaria configurada",
            ) from exc
        except (
            BoletaError,
            DispatchError,
            InvoiceError,
            RutError,
            TedError,
            ValueError,
        ) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _response(record, request)

    @app.get("/v1/fiscal-documents", response_model=list[DocumentResponse])
    def list_documents(
        request: Request,
        limit: int = 50,
        offset: int = 0,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[DocumentResponse]:
        try:
            records = ledger.list_documents(
                tenant_id=principal.tenant_id,
                limit=limit,
                offset=offset,
            )
        except FolioLedgerError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return [_response(record, request) for record in records]

    @app.get("/v1/fiscal-documents/{record_id}", response_model=DocumentResponse)
    def get_document(
        record_id: str,
        request: Request,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> DocumentResponse:
        record = ledger.document_by_id(record_id, tenant_id=principal.tenant_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        return _response(record, request)

    @app.get("/v1/fiscal-documents/{record_id}/xml")
    def get_document_xml(
        record_id: str,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> Response:
        record = ledger.document_by_id(record_id, tenant_id=principal.tenant_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        return Response(
            content=record.signed_xml,
            media_type="application/xml",
            headers={
                "Content-Disposition": f'attachment; filename="{record.document_id}.xml"',
                "X-Content-SHA256": record.xml_sha256,
                "Cache-Control": "private, no-store",
            },
        )
