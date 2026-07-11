"""Contratos puros entre el reader, el worker durable y Completo Fiscal."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import hashlib
import json
from typing import Any
from uuid import UUID


class ReaderResource(StrEnum):
    RCV = "rcv"
    F29 = "f29"
    BHE = "bhe"
    F22 = "f22"
    TAX_PROFILE = "tax_profile"


class ReaderRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    NEEDS_HUMAN = "needs_human"
    FAILED = "failed"


@dataclass(frozen=True)
class ReaderRun:
    id: UUID
    tenant_id: str
    resource: ReaderResource
    period: str
    status: ReaderRunStatus
    requested_at: datetime

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id es obligatorio")
        if not self.period.strip():
            raise ValueError("period es obligatorio")
        if self.requested_at.tzinfo is None:
            raise ValueError("requested_at debe incluir zona horaria")


@dataclass(frozen=True)
class SiiSnapshot:
    run_id: UUID
    tenant_id: str
    resource: ReaderResource
    period: str
    captured_at: datetime
    payload: dict[str, Any]
    payload_sha256: str

    @classmethod
    def create(
        cls,
        *,
        run_id: UUID,
        tenant_id: str,
        resource: ReaderResource,
        period: str,
        captured_at: datetime,
        payload: dict[str, Any],
    ) -> "SiiSnapshot":
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        return cls(
            run_id=run_id,
            tenant_id=tenant_id,
            resource=resource,
            period=period,
            captured_at=captured_at,
            payload=payload,
            payload_sha256=hashlib.sha256(canonical).hexdigest(),
        )

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.period.strip():
            raise ValueError("tenant_id y period son obligatorios")
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at debe incluir zona horaria")
        if len(self.payload_sha256) != 64:
            raise ValueError("payload_sha256 inválido")
