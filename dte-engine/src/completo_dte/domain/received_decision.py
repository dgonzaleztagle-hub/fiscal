"""Intenciones tributarias sobre documentos recibidos, sin transporte SII."""

from dataclasses import dataclass
from enum import StrEnum


class ReceivedDecisionError(ValueError):
    """La aceptación o reclamo solicitado es incoherente."""


class ReceivedDecisionType(StrEnum):
    ACCEPT_CONTENT = "accept_content"
    ACK_RECEIPT = "ack_receipt"
    CLAIM_CONTENT = "claim_content"
    CLAIM_PARTIAL_DELIVERY = "claim_partial_delivery"
    CLAIM_TOTAL_DELIVERY = "claim_total_delivery"

    @property
    def sii_code(self) -> str:
        return {
            self.ACCEPT_CONTENT: "ACD",
            self.ACK_RECEIPT: "ERM",
            self.CLAIM_CONTENT: "RCD",
            self.CLAIM_PARTIAL_DELIVERY: "RFP",
            self.CLAIM_TOTAL_DELIVERY: "RFT",
        }[self]


@dataclass(frozen=True)
class ReceivedDecision:
    decision: ReceivedDecisionType
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.decision in {
            ReceivedDecisionType.ACCEPT_CONTENT,
            ReceivedDecisionType.ACK_RECEIPT,
        } and self.reason is not None:
            raise ReceivedDecisionError("La aceptación o recibo no lleva razón de reclamo")
        if self.decision not in {
            ReceivedDecisionType.ACCEPT_CONTENT,
            ReceivedDecisionType.ACK_RECEIPT,
        }:
            if self.reason is None or not self.reason.strip():
                raise ReceivedDecisionError("El reclamo requiere una razón comprensible")
            try:
                size = len(self.reason.encode("iso-8859-1"))
            except UnicodeEncodeError as exc:
                raise ReceivedDecisionError("La razón contiene caracteres no admitidos") from exc
            if size > 200:
                raise ReceivedDecisionError("La razón del reclamo excede 200 bytes")
