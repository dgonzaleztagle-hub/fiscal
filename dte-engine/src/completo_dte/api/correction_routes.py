"""Rutas de notas de crédito/débito, anulación y corrección de texto."""

from collections.abc import Callable
from datetime import date

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from lxml import etree

from completo_dte.application import (
    AnnulDocumentCommand,
    CorrectTextCommand,
    IssueCorrectionCommand,
    IssueCorrectionService,
)
from completo_dte.domain import (
    CorrectionCode,
    CorrectionDocument,
    CorrectionError,
    CorrectionReference,
    DocumentType,
    FiscalLine,
    Issuer,
    Party,
    RutError,
    TedError,
)
from completo_dte.infrastructure import CafRangeExhausted, FolioLedger, FolioLedgerError

from .contracts import (
    AnnulmentRequest,
    CorrectionIssueRequest,
    DocumentResponse,
    TextCorrectionRequest,
)
from .projections import _response, _xml_one, _xml_optional
from .security import ApiPrincipal


def register_correction_routes(
    *,
    app: FastAPI,
    ledger: FolioLedger,
    authenticate: Callable[..., ApiPrincipal],
    issue_correction_service: IssueCorrectionService | None,
) -> None:
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
