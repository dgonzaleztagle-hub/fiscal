"""Plazo informativo para aceptación/reclamo de facturas recibidas."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class DecisionDeadlineStatus(StrEnum):
    UNKNOWN = "unknown"
    OPEN = "open"
    URGENT = "urgent"
    EXPIRED = "expired"


@dataclass(frozen=True)
class DecisionDeadline:
    status: DecisionDeadlineStatus
    expires_at: datetime | None
    remaining_seconds: int | None


def calculate_decision_deadline(
    sii_received_at: datetime | None, *, now: datetime
) -> DecisionDeadline:
    """Calcula ocho días corridos; nunca ejecuta una aceptación automática."""
    if sii_received_at is None:
        return DecisionDeadline(DecisionDeadlineStatus.UNKNOWN, None, None)
    if sii_received_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("Las fechas del plazo deben incluir zona horaria")
    expires_at = sii_received_at + timedelta(days=8)
    remaining = int((expires_at - now).total_seconds())
    if remaining <= 0:
        status = DecisionDeadlineStatus.EXPIRED
    elif remaining <= 24 * 60 * 60:
        status = DecisionDeadlineStatus.URGENT
    else:
        status = DecisionDeadlineStatus.OPEN
    return DecisionDeadline(status, expires_at, max(0, remaining))
