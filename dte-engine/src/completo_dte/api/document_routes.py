"""Rutas de emisión, consulta y corrección de documentos tributarios."""

from collections.abc import Callable
from datetime import date

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import Response
from lxml import etree

from completo_dte.application import (
    AnnulDocumentCommand,
    CorrectTextCommand,
    IssueBoletaCommand,
    IssueBoletaService,
    IssueCorrectionCommand,
    IssueCorrectionService,
    IssueDispatchCommand,
    IssueDispatchService,
    IssueInvoiceCommand,
    IssueInvoiceService,
)
from completo_dte.domain import (
    BoletaError,
    BoletaLine,
    CorrectionCode,
    CorrectionDocument,
    CorrectionError,
    CorrectionReference,
    DispatchError,
    DispatchTransport,
    DocumentType,
    FiscalDocumentDraft,
    FiscalDocumentError,
    FiscalLine,
    FiscalReference,
    InvoiceError,
    Issuer,
    Party,
    RutError,
    SchemaValidationError,
    TedError,
)
from completo_dte.infrastructure import CafRangeExhausted, FolioLedger, FolioLedgerError

from .contracts import (
    AnnulmentRequest,
    CorrectionIssueRequest,
    DocumentResponse,
    DraftValidationResponse,
    FiscalDraftRequest,
    FiscalLineRequest,
    IssueRequest,
    LineRequest,
    TextCorrectionRequest,
)
from .projections import _document_name, _response, _xml_one, _xml_optional
from .security import ApiPrincipal


def register_document_routes(
    *,
    app: FastAPI,
    ledger: FolioLedger,
    authenticate: Callable[..., ApiPrincipal],
    issue_service: IssueBoletaService,
    issue_invoice_service: IssueInvoiceService | None,
    issue_correction_service: IssueCorrectionService | None,
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
            issuer = Issuer(**payload.issuer.model_dump())
            if payload.document_type in {
                DocumentType.BOLETA_AFECTA,
                DocumentType.BOLETA_EXENTA,
            }:
                if not all(isinstance(line, LineRequest) for line in payload.lines):
                    raise ValueError("Las boletas requieren líneas con precio bruto")
                command = IssueBoletaCommand(
                    tenant_id=principal.tenant_id,
                    idempotency_key=idempotency_key,
                    issuer=issuer,
                    issued_on=payload.issued_on,
                    lines=tuple(
                        BoletaLine(**line.model_dump())
                        for line in payload.lines
                        if isinstance(line, LineRequest)
                    ),
                    receiver_rut=payload.receiver_rut,
                    receiver_name=payload.receiver_name,
                    reference_code=payload.reference.code
                    if payload.reference
                    else None,
                    reference_reason=payload.reference.reason
                    if payload.reference
                    else None,
                    document_type=int(payload.document_type),
                )
                record = issue_service.issue(command)
            elif payload.document_type in {
                DocumentType.FACTURA_AFECTA,
                DocumentType.FACTURA_EXENTA,
            }:
                if issue_invoice_service is None:
                    raise HTTPException(
                        status_code=503,
                        detail="La emisión de facturas no está configurada en este entorno",
                    )
                if payload.receiver is None:
                    raise ValueError("La factura requiere receptor identificado")
                if not all(
                    isinstance(line, FiscalLineRequest) for line in payload.lines
                ):
                    raise ValueError(
                        "Las facturas requieren líneas tributarias con precio neto"
                    )
                draft = FiscalDocumentDraft(
                    tenant_id=principal.tenant_id,
                    branch_id=payload.branch_id,
                    issuer_profile_id=payload.issuer_profile_id,
                    document_type=payload.document_type,
                    issued_on=payload.issued_on,
                    receiver=Party(**payload.receiver.model_dump()),
                    lines=tuple(
                        FiscalLine(**line.model_dump())
                        for line in payload.lines
                        if isinstance(line, FiscalLineRequest)
                    ),
                    payment_terms=payload.payment_terms,
                    due_on=payload.due_on,
                )
                record = issue_invoice_service.issue(
                    IssueInvoiceCommand(
                        idempotency_key=idempotency_key,
                        issuer=issuer,
                        draft=draft,
                    )
                )
            elif payload.document_type is DocumentType.GUIA_DESPACHO:
                if issue_dispatch_service is None:
                    raise HTTPException(
                        status_code=503,
                        detail="La emisión de guías no está configurada en este entorno",
                    )
                if payload.receiver is None:
                    raise ValueError("La guía requiere receptor identificado")
                if payload.dispatch_reason is None:
                    raise ValueError("La guía requiere motivo del traslado")
                if not all(
                    isinstance(line, FiscalLineRequest) for line in payload.lines
                ):
                    raise ValueError("Las guías requieren líneas tributarias")
                draft = FiscalDocumentDraft(
                    tenant_id=principal.tenant_id,
                    branch_id=payload.branch_id,
                    issuer_profile_id=payload.issuer_profile_id,
                    document_type=payload.document_type,
                    issued_on=payload.issued_on,
                    receiver=Party(**payload.receiver.model_dump()),
                    lines=tuple(
                        FiscalLine(**line.model_dump())
                        for line in payload.lines
                        if isinstance(line, FiscalLineRequest)
                    ),
                    dispatch_reason=payload.dispatch_reason,
                )
                record = issue_dispatch_service.issue(
                    IssueDispatchCommand(
                        idempotency_key=idempotency_key,
                        issuer=issuer,
                        draft=draft,
                        dispatch_account=payload.dispatch_account,
                        transport=DispatchTransport(
                            **(
                                payload.transport.model_dump()
                                if payload.transport
                                else {}
                            )
                        ),
                    )
                )
            else:
                raise ValueError(
                    "Este tipo documental todavía no tiene emisor implementado"
                )
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

    @app.post(
        "/v1/fiscal-documents/{record_id}/corrections",
        response_model=DocumentResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def issue_amount_correction(
        record_id: str,
        payload: CorrectionIssueRequest,
        request: Request,
        principal: ApiPrincipal = Depends(authenticate),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> DocumentResponse:
        if issue_correction_service is None:
            raise HTTPException(
                status_code=503, detail="Las correcciones no están configuradas"
            )
        if not idempotency_key or not idempotency_key.strip():
            raise HTTPException(
                status_code=400, detail="Idempotency-Key es obligatorio"
            )
        if payload.document_type not in {
            DocumentType.NOTA_DEBITO,
            DocumentType.NOTA_CREDITO,
        }:
            raise HTTPException(status_code=422, detail="Use nota 56 o 61")
        target = ledger.document_by_id(record_id, tenant_id=principal.tenant_id)
        if target is None:
            raise HTTPException(
                status_code=404, detail="Documento original no encontrado"
            )
        try:
            root = etree.fromstring(
                target.signed_xml,
                etree.XMLParser(resolve_entities=False, no_network=True),
            )
            receiver = Party(
                rut=_xml_one(root, "RUTRecep"),
                legal_name=_xml_one(root, "RznSocRecep"),
                business_activity=_xml_one(root, "GiroRecep"),
                address=_xml_one(root, "DirRecep"),
                commune=_xml_one(root, "CmnaRecep"),
                email=_xml_optional(root, "CorreoRecep"),
            )
            correction = CorrectionDocument(
                issuer=Issuer(**payload.issuer.model_dump()),
                receiver=receiver,
                document_type=payload.document_type,
                folio=1,
                issued_on=payload.issued_on,
                lines=tuple(FiscalLine(**line.model_dump()) for line in payload.lines),
                reference=CorrectionReference(
                    document_type=DocumentType(target.document_type),
                    folio=target.folio,
                    issued_on=date.fromisoformat(_xml_one(root, "FchEmis")),
                    code=CorrectionCode.FIX_AMOUNT,
                    reason=payload.reason,
                ),
            )
            note = issue_correction_service.issue(
                IssueCorrectionCommand(
                    tenant_id=principal.tenant_id,
                    idempotency_key=idempotency_key,
                    target_record_id=target.id,
                    correction=correction,
                )
            )
        except CafRangeExhausted as exc:
            raise HTTPException(
                status_code=409, detail="No quedan folios disponibles"
            ) from exc
        except FolioLedgerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (CorrectionError, RutError, TedError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _response(note, request)

    @app.post(
        "/v1/fiscal-documents/{record_id}/annulment",
        response_model=DocumentResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def annul_fiscal_document(
        record_id: str,
        payload: AnnulmentRequest,
        request: Request,
        principal: ApiPrincipal = Depends(authenticate),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> DocumentResponse:
        if issue_correction_service is None:
            raise HTTPException(
                status_code=503, detail="Las correcciones no están configuradas"
            )
        if not idempotency_key or not idempotency_key.strip():
            raise HTTPException(
                status_code=400, detail="Idempotency-Key es obligatorio"
            )
        try:
            note = issue_correction_service.annul(
                AnnulDocumentCommand(
                    tenant_id=principal.tenant_id,
                    idempotency_key=idempotency_key,
                    target_record_id=record_id,
                    issued_on=payload.issued_on,
                )
            )
        except CafRangeExhausted as exc:
            raise HTTPException(
                status_code=409, detail="No quedan folios disponibles"
            ) from exc
        except FolioLedgerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (CorrectionError, RutError, TedError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _response(note, request)

    @app.post(
        "/v1/fiscal-documents/{record_id}/corrections/text",
        response_model=DocumentResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def correct_fiscal_document_text(
        record_id: str,
        payload: TextCorrectionRequest,
        request: Request,
        principal: ApiPrincipal = Depends(authenticate),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> DocumentResponse:
        if issue_correction_service is None:
            raise HTTPException(
                status_code=503, detail="Las correcciones no están configuradas"
            )
        if not idempotency_key or not idempotency_key.strip():
            raise HTTPException(
                status_code=400, detail="Idempotency-Key es obligatorio"
            )
        try:
            note = issue_correction_service.correct_text(
                CorrectTextCommand(
                    tenant_id=principal.tenant_id,
                    idempotency_key=idempotency_key,
                    target_record_id=record_id,
                    issued_on=payload.issued_on,
                    business_activity=payload.business_activity,
                    address=payload.address,
                    commune=payload.commune,
                )
            )
        except CafRangeExhausted as exc:
            raise HTTPException(
                status_code=409, detail="No quedan folios disponibles"
            ) from exc
        except FolioLedgerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (CorrectionError, RutError, TedError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _response(note, request)

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
