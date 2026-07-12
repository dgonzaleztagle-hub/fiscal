"""Frontera HTTP para emitir y recuperar boletas firmadas."""

from datetime import date

from lxml import etree

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response

from completo_dte.application import (
    AnnulDocumentCommand,
    CorrectTextCommand,
    IssueBoletaCommand,
    IssueBoletaService,
    IssueDispatchCommand,
    IssueDispatchService,
    IssueCorrectionCommand,
    IssueCorrectionService,
    IssueInvoiceCommand,
    InvoiceDeliveryService,
    IssueInvoiceService,
    ReceivedDecisionService,
    RcvReconciliationService,
    MonthlyReportBuilder,
    AccountantPackageBuilder,
)
from completo_dte.domain import (
    BoletaError,
    BoletaLine,
    CorrectionDocument,
    CorrectionError,
    CorrectionReference,
    CorrectionCode,
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
    ReceivedDocumentError,
    ReceivedDocumentValidator,
    ReceivedDecision,
    ReceivedDecisionError,
    RcvPeriod,
    RcvPurchaseEntry,
    PurchaseLineAllocation,
    RutError,
    SchemaValidationError,
    TedError,
)
from completo_dte.infrastructure import (
    CafRangeExhausted,
    FolioLedger,
    FolioLedgerError,
    RcvRepository,
)
from completo_dte.presentation import (
    BoletaReceiptRenderer,
    InvoiceReceiptRenderer,
    ReceiptError,
)
from .security import ApiPrincipal, build_authenticator
from .projections import (
    _delivery_response,
    _document_name,
    _rcv_snapshot_response,
    _received_classification_response,
    _received_decision_response,
    _received_response,
    _response,
    _xml_optional,
    _xml_one,
)
from .contracts import (
    LineRequest,
    DocumentResponse,
    FiscalLineRequest,
    FiscalDraftRequest,
    IssueRequest,
    DraftValidationResponse,
    EventResponse,
    EnvelopeResponse,
    OperationalAlertResponse,
    DeliveryRequest,
    DeliveryResponse,
    CorrectionIssueRequest,
    AnnulmentRequest,
    TextCorrectionRequest,
    ReceivedDocumentResponse,
    ReceivedDecisionRequest,
    ReceivedDecisionResponse,
    ReceivedClassificationRequest,
    ReceivedClassificationResponse,
    RcvImportRequest,
    RcvSnapshotResponse,
    RcvDifferenceResponse,
    PurchaseAllocationsRequest,
)


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
) -> FastAPI:
    """Crea una app inyectable; no lee secretos ni abre bases al importar."""
    authenticate = build_authenticator(api_keys)

    app = FastAPI(
        title="Completo DTE Engine",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )

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

    @app.post(
        "/v1/received-documents/import",
        response_model=ReceivedDocumentResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def import_received_document(
        request: Request,
        source: str = "upload",
        principal: ApiPrincipal = Depends(authenticate),
    ) -> ReceivedDocumentResponse:
        if received_document_validator is None or resolve_tenant_taxpayer_rut is None:
            raise HTTPException(
                status_code=503, detail="La recepción no está configurada"
            )
        if request.headers.get("content-type", "").split(";", 1)[0] not in {
            "application/xml",
            "text/xml",
        }:
            raise HTTPException(status_code=415, detail="Se requiere XML tributario")
        try:
            expected_rut = resolve_tenant_taxpayer_rut(principal.tenant_id)
            received = received_document_validator.validate(
                await request.body(), expected_receiver_rut=expected_rut
            )
            record = ledger.import_received_document(
                tenant_id=principal.tenant_id,
                document=received,
                source=source,
            )
        except ReceivedDocumentError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except FolioLedgerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _received_response(record)

    @app.get(
        "/v1/received-documents",
        response_model=list[ReceivedDocumentResponse],
    )
    def list_received_documents(
        document_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[ReceivedDocumentResponse]:
        try:
            records = ledger.list_received_documents(
                tenant_id=principal.tenant_id,
                status=document_status,
                limit=limit,
                offset=offset,
            )
        except FolioLedgerError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return [_received_response(record) for record in records]

    @app.post(
        "/v1/received-documents/{record_id}/decision",
        response_model=ReceivedDecisionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def decide_received_document(
        record_id: str,
        payload: ReceivedDecisionRequest,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> ReceivedDecisionResponse:
        if received_decision_service is None:
            raise HTTPException(
                status_code=503, detail="Las decisiones no están configuradas"
            )
        try:
            prepared = received_decision_service.prepare(
                tenant_id=principal.tenant_id,
                received_document_id=record_id,
                intent=ReceivedDecision(payload.decision, payload.reason),
            )
            final = (
                received_decision_service.submit(prepared)
                if prepared.status.value == "prepared"
                else prepared
            )
        except ReceivedDecisionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except FolioLedgerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _received_decision_response(final)

    @app.post(
        "/v1/received-decisions/{decision_id}/reconcile",
        response_model=ReceivedDecisionResponse,
    )
    def reconcile_received_decision(
        decision_id: str,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> ReceivedDecisionResponse:
        if received_decision_service is None:
            raise HTTPException(
                status_code=503, detail="Las decisiones no están configuradas"
            )
        decision = ledger.received_decision_by_id(
            decision_id, tenant_id=principal.tenant_id
        )
        if decision is None:
            raise HTTPException(status_code=404, detail="Decisión no encontrada")
        try:
            final = received_decision_service.reconcile(decision)
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _received_decision_response(final)

    @app.post(
        "/v1/received-documents/{record_id}/classification",
        response_model=ReceivedClassificationResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def classify_received_document(
        record_id: str,
        payload: ReceivedClassificationRequest,
        principal: ApiPrincipal = Depends(authenticate),
        actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    ) -> ReceivedClassificationResponse:
        if not actor_id:
            raise HTTPException(status_code=400, detail="X-Actor-Id es obligatorio")
        try:
            record = ledger.classify_received_document(
                tenant_id=principal.tenant_id,
                received_document_id=record_id,
                provider_id=payload.provider_id,
                destination=payload.destination,
                category_code=payload.category_code,
                notes=payload.notes,
                classified_by=actor_id,
            )
        except FolioLedgerError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _received_classification_response(record)

    @app.get(
        "/v1/received-documents/{record_id}/classification",
        response_model=ReceivedClassificationResponse | None,
    )
    def get_received_classification(
        record_id: str,
        principal: ApiPrincipal = Depends(authenticate),
    ):
        record = ledger.latest_received_classification(
            record_id, tenant_id=principal.tenant_id
        )
        return _received_classification_response(record) if record else None

    @app.post(
        "/v1/received-classifications/{classification_id}/line-allocations",
        status_code=status.HTTP_201_CREATED,
    )
    def allocate_received_lines(
        classification_id: str,
        payload: PurchaseAllocationsRequest,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[dict[str, object]]:
        try:
            records = ledger.allocate_received_lines(
                tenant_id=principal.tenant_id,
                classification_id=classification_id,
                allocations=tuple(
                    PurchaseLineAllocation(**item.model_dump())
                    for item in payload.allocations
                ),
            )
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return [
            {
                "classification_id": record.classification_id,
                "line_number": record.line_number,
                "destination": record.destination,
                "control_plane_ref": record.control_plane_ref,
            }
            for record in records
        ]

    @app.post(
        "/v1/rcv/purchases/snapshots",
        response_model=RcvSnapshotResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def import_rcv_snapshot(
        payload: RcvImportRequest,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> RcvSnapshotResponse:
        if rcv_repository is None:
            raise HTTPException(status_code=503, detail="RCV no está configurado")
        try:
            snapshot = rcv_repository.import_snapshot(
                tenant_id=principal.tenant_id,
                period=RcvPeriod(payload.year, payload.month),
                entries=tuple(
                    RcvPurchaseEntry(**entry.model_dump()) for entry in payload.entries
                ),
                source=payload.source,
            )
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _rcv_snapshot_response(snapshot)

    @app.get(
        "/v1/rcv/purchases/{year}/{month}/reconciliation",
        response_model=list[RcvDifferenceResponse],
    )
    def reconcile_rcv_snapshot(
        year: int,
        month: int,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[RcvDifferenceResponse]:
        if rcv_repository is None or rcv_reconciliation_service is None:
            raise HTTPException(status_code=503, detail="RCV no está configurado")
        try:
            period = RcvPeriod(year, month)
            snapshot = rcv_repository.latest_snapshot(
                tenant_id=principal.tenant_id, period=period
            )
            if snapshot is None:
                raise HTTPException(
                    status_code=404, detail="Snapshot RCV no encontrado"
                )
            differences = rcv_reconciliation_service.reconcile(
                tenant_id=principal.tenant_id, snapshot=snapshot
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return [
            RcvDifferenceResponse(**difference.__dict__) for difference in differences
        ]

    @app.get("/v1/reports/monthly/{year}/{month}.csv")
    def export_monthly_csv(
        year: int,
        month: int,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> Response:
        try:
            RcvPeriod(year, month)
            outgoing = []
            received = []
            offset = 0
            while True:
                page = ledger.list_documents(
                    tenant_id=principal.tenant_id, limit=200, offset=offset
                )
                outgoing.extend(page)
                if len(page) < 200:
                    break
                offset += 200
            offset = 0
            while True:
                page = ledger.list_received_documents(
                    tenant_id=principal.tenant_id, limit=200, offset=offset
                )
                received.extend(page)
                if len(page) < 200:
                    break
                offset += 200
            builder = MonthlyReportBuilder()
            report = builder.build(
                year=year,
                month=month,
                outgoing=outgoing,
                received=received,
            )
            artifact = builder.csv(report)
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(
            artifact.content,
            media_type=artifact.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{artifact.filename}"',
                "X-Content-SHA256": artifact.sha256,
                "Cache-Control": "private, no-store",
            },
        )

    @app.get("/v1/reports/monthly/{year}/{month}.xlsx")
    def export_monthly_xlsx(
        year: int,
        month: int,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> Response:
        try:
            RcvPeriod(year, month)
            outgoing = []
            received = []
            offset = 0
            while True:
                page = ledger.list_documents(
                    tenant_id=principal.tenant_id, limit=200, offset=offset
                )
                outgoing.extend(page)
                if len(page) < 200:
                    break
                offset += 200
            offset = 0
            while True:
                page = ledger.list_received_documents(
                    tenant_id=principal.tenant_id, limit=200, offset=offset
                )
                received.extend(page)
                if len(page) < 200:
                    break
                offset += 200
            builder = MonthlyReportBuilder()
            artifact = builder.xlsx(
                builder.build(
                    year=year,
                    month=month,
                    outgoing=outgoing,
                    received=received,
                )
            )
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(
            artifact.content,
            media_type=artifact.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{artifact.filename}"',
                "X-Content-SHA256": artifact.sha256,
                "Cache-Control": "private, no-store",
            },
        )

    @app.get("/v1/reports/monthly/{year}/{month}.pdf")
    def export_monthly_pdf(
        year: int,
        month: int,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> Response:
        try:
            RcvPeriod(year, month)
            outgoing = []
            received = []
            offset = 0
            while True:
                page = ledger.list_documents(
                    tenant_id=principal.tenant_id, limit=200, offset=offset
                )
                outgoing.extend(page)
                if len(page) < 200:
                    break
                offset += 200
            offset = 0
            while True:
                page = ledger.list_received_documents(
                    tenant_id=principal.tenant_id, limit=200, offset=offset
                )
                received.extend(page)
                if len(page) < 200:
                    break
                offset += 200
            builder = MonthlyReportBuilder()
            artifact = builder.pdf(
                builder.build(
                    year=year, month=month, outgoing=outgoing, received=received
                )
            )
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(
            artifact.content,
            media_type=artifact.media_type,
            headers={
                "Content-Disposition": f'inline; filename="{artifact.filename}"',
                "X-Content-SHA256": artifact.sha256,
                "Cache-Control": "private, no-store",
            },
        )

    @app.get("/v1/reports/monthly/{year}/{month}/accountant-package.zip")
    def export_accountant_package(
        year: int,
        month: int,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> Response:
        try:
            RcvPeriod(year, month)
            outgoing = []
            received = []
            offset = 0
            while True:
                page = ledger.list_documents(
                    tenant_id=principal.tenant_id, limit=200, offset=offset
                )
                outgoing.extend(page)
                if len(page) < 200:
                    break
                offset += 200
            offset = 0
            while True:
                page = ledger.list_received_documents(
                    tenant_id=principal.tenant_id, limit=200, offset=offset
                )
                received.extend(page)
                if len(page) < 200:
                    break
                offset += 200
            report = MonthlyReportBuilder().build(
                year=year, month=month, outgoing=outgoing, received=received
            )
            package = AccountantPackageBuilder().build(
                report=report, outgoing=outgoing, received=received
            )
        except (FolioLedgerError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(
            package.content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{package.filename}"',
                "X-Content-SHA256": package.sha256,
                "Cache-Control": "private, no-store",
            },
        )

    @app.get(
        "/v1/fiscal-documents/{record_id}/events",
        response_model=list[EventResponse],
    )
    def get_document_events(
        record_id: str,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[EventResponse]:
        record = ledger.document_by_id(record_id, tenant_id=principal.tenant_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        return [EventResponse(**event) for event in ledger.events(record.lease_id)]

    @app.get("/v1/fiscal-documents/{record_id}/pdf")
    def get_document_pdf(
        record_id: str,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> Response:
        record = ledger.document_by_id(record_id, tenant_id=principal.tenant_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        if resolve_receipt_config is None or record.document_type not in {
            33,
            34,
            39,
            41,
            52,
            56,
            61,
        }:
            raise HTTPException(status_code=503, detail="Representación no disponible")
        try:
            config = resolve_receipt_config(record.tenant_id, record.taxpayer_rut)
            renderer = (
                BoletaReceiptRenderer()
                if record.document_type in {39, 41}
                else InvoiceReceiptRenderer()
            )
            pdf = renderer.render(record.signed_xml, config)
        except (ReceiptError, ValueError) as exc:
            raise HTTPException(
                status_code=503, detail="Representación no disponible"
            ) from exc
        return Response(
            pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{record.document_id}.pdf"',
                "Cache-Control": "private, no-store",
            },
        )

    @app.post(
        "/v1/fiscal-documents/{record_id}/deliveries",
        response_model=DeliveryResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def queue_invoice_delivery(
        record_id: str,
        payload: DeliveryRequest,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> DeliveryResponse:
        if invoice_delivery_service is None:
            raise HTTPException(
                status_code=503,
                detail="La entrega de facturas no está configurada en este entorno",
            )
        record = ledger.document_by_id(record_id, tenant_id=principal.tenant_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        try:
            delivery = invoice_delivery_service.queue(
                record,
                recipient_email=payload.recipient_email,
            )
        except (FolioLedgerError, ReceiptError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _delivery_response(delivery)

    @app.get(
        "/v1/fiscal-deliveries/{delivery_id}",
        response_model=DeliveryResponse,
    )
    def get_fiscal_delivery(
        delivery_id: str,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> DeliveryResponse:
        delivery = ledger.delivery_by_id(delivery_id, tenant_id=principal.tenant_id)
        if delivery is None:
            raise HTTPException(status_code=404, detail="Entrega no encontrada")
        return _delivery_response(delivery)

    @app.get("/v1/fiscal-envelopes", response_model=list[EnvelopeResponse])
    def list_fiscal_envelopes(
        limit: int = 100,
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[EnvelopeResponse]:
        try:
            envelopes = ledger.list_envelopes(
                tenant_id=principal.tenant_id,
                limit=limit,
            )
        except FolioLedgerError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return [
            EnvelopeResponse(
                **{
                    "id": envelope.id,
                    "kind": envelope.kind,
                    "document_id": envelope.document_id,
                    "taxpayer_rut": envelope.taxpayer_rut,
                    "status": envelope.status.value,
                    "track_id": envelope.track_id,
                    "xml_sha256": envelope.xml_sha256,
                    "created_at": envelope.created_at,
                    "updated_at": envelope.updated_at,
                }
            )
            for envelope in envelopes
        ]

    @app.get(
        "/v1/operational-alerts",
        response_model=list[OperationalAlertResponse],
    )
    def operational_alerts(
        principal: ApiPrincipal = Depends(authenticate),
    ) -> list[OperationalAlertResponse]:
        return [
            OperationalAlertResponse(**alert)
            for alert in ledger.operational_alerts(tenant_id=principal.tenant_id)
        ]

    @app.get("/public/v1/boletas/{public_id}", response_class=HTMLResponse)
    def public_receipt_page(public_id: str, request: Request) -> HTMLResponse:
        record = ledger.document_by_public_id(public_id)
        if record is None or resolve_receipt_config is None:
            raise HTTPException(status_code=404, detail="Boleta no encontrada")
        pdf_url = str(request.url_for("public_receipt_pdf", public_id=public_id))
        body = (
            '<!doctype html><html lang="es-CL"><head>'
            '<meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<meta name="robots" content="noindex,nofollow">'
            "<title>Boleta electrónica</title></head>"
            '<body style="font-family:system-ui;max-width:42rem;margin:3rem auto;padding:1rem">'
            "<h1>Boleta electrónica</h1>"
            f"<p>Emisor: {_html(record.taxpayer_rut)}</p>"
            f"<p>Tipo {record.document_type}, folio {record.folio}</p>"
            f"<p>Emitida: {_html(record.created_at[:10])}</p>"
            f'<p><a href="{_html(pdf_url)}">Ver representación de la boleta (PDF)</a></p>'
            "</body></html>"
        )
        return HTMLResponse(
            body,
            headers={
                "Cache-Control": "private, max-age=300",
                "X-Robots-Tag": "noindex",
            },
        )

    @app.get("/public/v1/boletas/{public_id}/pdf", name="public_receipt_pdf")
    def public_receipt_pdf(public_id: str) -> Response:
        record = ledger.document_by_public_id(public_id)
        if record is None or resolve_receipt_config is None:
            raise HTTPException(status_code=404, detail="Boleta no encontrada")
        try:
            config = resolve_receipt_config(record.tenant_id, record.taxpayer_rut)
            pdf = BoletaReceiptRenderer().render(record.signed_xml, config)
        except (ReceiptError, ValueError) as exc:
            raise HTTPException(
                status_code=503, detail="Representación no disponible"
            ) from exc
        return Response(
            pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="boleta-{record.folio}.pdf"',
                "Cache-Control": "private, max-age=300",
                "X-Robots-Tag": "noindex",
            },
        )

    return app


def _html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
