"""Cliente oficial de la API de Boleta Electrónica del SII."""

from .boleta_api import (
    EnvelopeOutcome,
    RemoteEnvelopeStatus,
    SeedSigner,
    SiiApiError,
    SiiBoletaApi,
    UploadReceipt,
    classify_envelope_status,
)
from .legacy_dte import LegacyEnvelopeStatus, LegacyUploadReceipt, SiiLegacyDteApi
from .received_registry import (
    ReceivedRegistryCodecError,
    ReceivedRegistrySoapCodec,
    RegistryResponse,
)

__all__ = [
    "EnvelopeOutcome",
    "RemoteEnvelopeStatus",
    "SeedSigner",
    "SiiApiError",
    "SiiBoletaApi",
    "UploadReceipt",
    "classify_envelope_status",
    "LegacyEnvelopeStatus",
    "LegacyUploadReceipt",
    "SiiLegacyDteApi",
    "ReceivedRegistryCodecError",
    "ReceivedRegistrySoapCodec",
    "RegistryResponse",
]
