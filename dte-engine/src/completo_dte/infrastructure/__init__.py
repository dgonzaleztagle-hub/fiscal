"""Adaptadores de persistencia del motor DTE."""

from .backup import BackupError, BackupManifest, SqliteBackupService
from .credential_registry import CredentialReferenceRecord, CredentialReferenceRegistry
from .folio_ledger import FolioLedger
from .monthly_close_ledger import MonthlyCloseRecord, MonthlyCloseReviewRecord
from .payment_ledger import ElectronicPaymentRecord, PaymentReconciliationRecord
from .commercial_ledger import CommercialRecord
from .inventory_ledger import InventoryMovementRecord, InventoryProductRecord
from .treasury_ledger import ApprovalRecord, ObligationRecord
from .rcv_repository import RcvEntryRecord, RcvRepository, RcvSnapshotRecord
from .records import (
    AttemptState,
    CafRangeExhausted,
    DeliveryState,
    EnvelopeState,
    FiscalDeliveryRecord,
    FiscalDocumentRecord,
    FiscalEnvelopeRecord,
    FolioLease,
    FolioLedgerError,
    LeaseState,
    ReceivedClassificationRecord,
    ReceivedDecisionAttemptRecord,
    ReceivedDecisionRecord,
    ReceivedDecisionState,
    ReceivedFiscalDocumentRecord,
    ReceivedLineAllocationRecord,
    ReceivedLineRecord,
    ReceivedSiiObservationRecord,
    SubmissionAttemptRecord,
)

__all__ = [
    "AttemptState",
    "CafRangeExhausted",
    "DeliveryState",
    "EnvelopeState",
    "FiscalDocumentRecord",
    "FiscalDeliveryRecord",
    "FiscalEnvelopeRecord",
    "FolioLease",
    "FolioLedger",
    "MonthlyCloseRecord",
    "MonthlyCloseReviewRecord",
    "ElectronicPaymentRecord",
    "PaymentReconciliationRecord",
    "CommercialRecord",
    "InventoryMovementRecord",
    "InventoryProductRecord",
    "ApprovalRecord",
    "ObligationRecord",
    "FolioLedgerError",
    "LeaseState",
    "SubmissionAttemptRecord",
    "RcvEntryRecord",
    "RcvRepository",
    "RcvSnapshotRecord",
    "BackupError",
    "BackupManifest",
    "SqliteBackupService",
    "CredentialReferenceRecord",
    "CredentialReferenceRegistry",
    "ReceivedFiscalDocumentRecord",
    "ReceivedDecisionAttemptRecord",
    "ReceivedDecisionRecord",
    "ReceivedDecisionState",
    "ReceivedClassificationRecord",
    "ReceivedSiiObservationRecord",
    "ReceivedLineRecord",
    "ReceivedLineAllocationRecord",
]
