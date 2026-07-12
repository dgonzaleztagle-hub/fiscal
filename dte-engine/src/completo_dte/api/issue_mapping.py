"""Mapeo explícito desde contratos HTTP hacia comandos de emisión."""

from completo_dte.application import (
    IssueBoletaCommand,
    IssueBoletaService,
    IssueDispatchCommand,
    IssueDispatchService,
    IssueInvoiceCommand,
    IssueInvoiceService,
)
from completo_dte.domain import (
    BoletaLine,
    DispatchTransport,
    DocumentType,
    FiscalDocumentDraft,
    FiscalLine,
    Issuer,
    Party,
)
from completo_dte.infrastructure import FiscalDocumentRecord

from .contracts import FiscalLineRequest, IssueRequest, LineRequest


class IssueServiceUnavailable(RuntimeError):
    """El tipo es válido, pero su emisor no fue configurado en este entorno."""


def issue_from_request(
    *,
    payload: IssueRequest,
    tenant_id: str,
    idempotency_key: str,
    issue_service: IssueBoletaService,
    issue_invoice_service: IssueInvoiceService | None,
    issue_dispatch_service: IssueDispatchService | None,
) -> FiscalDocumentRecord:
    issuer = Issuer(**payload.issuer.model_dump())
    if payload.document_type in {
        DocumentType.BOLETA_AFECTA,
        DocumentType.BOLETA_EXENTA,
    }:
        return _issue_boleta(payload, tenant_id, idempotency_key, issuer, issue_service)
    if payload.document_type in {
        DocumentType.FACTURA_AFECTA,
        DocumentType.FACTURA_EXENTA,
    }:
        if issue_invoice_service is None:
            raise IssueServiceUnavailable(
                "La emisión de facturas no está configurada en este entorno"
            )
        return _issue_invoice(
            payload, tenant_id, idempotency_key, issuer, issue_invoice_service
        )
    if payload.document_type is DocumentType.GUIA_DESPACHO:
        if issue_dispatch_service is None:
            raise IssueServiceUnavailable(
                "La emisión de guías no está configurada en este entorno"
            )
        return _issue_dispatch(
            payload, tenant_id, idempotency_key, issuer, issue_dispatch_service
        )
    raise ValueError("Este tipo documental todavía no tiene emisor implementado")


def _issue_boleta(
    payload: IssueRequest,
    tenant_id: str,
    idempotency_key: str,
    issuer: Issuer,
    service: IssueBoletaService,
) -> FiscalDocumentRecord:
    if not all(isinstance(line, LineRequest) for line in payload.lines):
        raise ValueError("Las boletas requieren líneas con precio bruto")
    return service.issue(
        IssueBoletaCommand(
            tenant_id=tenant_id,
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
            reference_code=payload.reference.code if payload.reference else None,
            reference_reason=payload.reference.reason if payload.reference else None,
            document_type=int(payload.document_type),
        )
    )


def _fiscal_lines(payload: IssueRequest, family: str) -> tuple[FiscalLine, ...]:
    if not all(isinstance(line, FiscalLineRequest) for line in payload.lines):
        raise ValueError(f"Las {family} requieren líneas tributarias")
    return tuple(
        FiscalLine(**line.model_dump())
        for line in payload.lines
        if isinstance(line, FiscalLineRequest)
    )


def _receiver(payload: IssueRequest, family: str) -> Party:
    if payload.receiver is None:
        raise ValueError(f"La {family} requiere receptor identificado")
    return Party(**payload.receiver.model_dump())


def _issue_invoice(
    payload: IssueRequest,
    tenant_id: str,
    idempotency_key: str,
    issuer: Issuer,
    service: IssueInvoiceService,
) -> FiscalDocumentRecord:
    draft = FiscalDocumentDraft(
        tenant_id=tenant_id,
        branch_id=payload.branch_id,
        issuer_profile_id=payload.issuer_profile_id,
        document_type=payload.document_type,
        issued_on=payload.issued_on,
        receiver=_receiver(payload, "factura"),
        lines=_fiscal_lines(payload, "facturas"),
        payment_terms=payload.payment_terms,
        due_on=payload.due_on,
    )
    return service.issue(
        IssueInvoiceCommand(
            idempotency_key=idempotency_key,
            issuer=issuer,
            draft=draft,
        )
    )


def _issue_dispatch(
    payload: IssueRequest,
    tenant_id: str,
    idempotency_key: str,
    issuer: Issuer,
    service: IssueDispatchService,
) -> FiscalDocumentRecord:
    if payload.dispatch_reason is None:
        raise ValueError("La guía requiere motivo del traslado")
    draft = FiscalDocumentDraft(
        tenant_id=tenant_id,
        branch_id=payload.branch_id,
        issuer_profile_id=payload.issuer_profile_id,
        document_type=payload.document_type,
        issued_on=payload.issued_on,
        receiver=_receiver(payload, "guía"),
        lines=_fiscal_lines(payload, "guías"),
        dispatch_reason=payload.dispatch_reason,
    )
    return service.issue(
        IssueDispatchCommand(
            idempotency_key=idempotency_key,
            issuer=issuer,
            draft=draft,
            dispatch_account=payload.dispatch_account,
            transport=DispatchTransport(
                **(payload.transport.model_dump() if payload.transport else {})
            ),
        )
    )
