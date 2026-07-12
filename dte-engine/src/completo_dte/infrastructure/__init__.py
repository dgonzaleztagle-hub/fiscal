"""Adaptadores de persistencia del motor DTE."""

from .backup import BackupError, BackupManifest, SqliteBackupService
from .credential_registry import CredentialReferenceRecord, CredentialReferenceRegistry
from .folio_ledger import FolioLedger
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
