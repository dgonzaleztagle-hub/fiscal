"""Bootstrap operacional de un tenant para el servidor local."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
import os
from pathlib import Path

from completo_dte.application import IssueBoletaService
from completo_dte.domain import (
    CafAuthenticityValidator,
    CafLoader,
    CertificateLoader,
    EnvelopeAuthorization,
    EnvioBoletaBuilder,
    SiiCertificateStore,
    TrustedCafAuthorization,
    XmlSchemaValidator,
)
from completo_dte.infrastructure import FolioLedger
from completo_dte.presentation import ReceiptConfig

from .app import create_app


class ConfigurationError(RuntimeError):
    """La API no tiene toda la configuración segura requerida."""


@dataclass(frozen=True)
class LocalSettings:
    database_path: Path
    tenant_id: str
    api_key: str
    caf_path: Path
    sii_certificate_path: Path
    sii_certificate_sha256: str
    pfx_path: Path
    pfx_password: str
    envio_boleta_xsd_path: Path
    resolution_date: date
    resolution_number: int
    verification_url: str

    @classmethod
    def from_environment(cls) -> "LocalSettings":
        values = {
            name: os.environ.get(name, "").strip()
            for name in (
                "DTE_DATABASE_PATH",
                "DTE_TENANT_ID",
                "DTE_API_KEY",
                "DTE_CAF_PATH",
                "DTE_SII_CERTIFICATE_PATH",
                "DTE_SII_CERTIFICATE_SHA256",
                "DTE_PFX_PATH",
                "DTE_PFX_PASSWORD",
                "DTE_ENVIO_BOLETA_XSD_PATH",
                "DTE_RESOLUTION_DATE",
                "DTE_RESOLUTION_NUMBER",
                "DTE_VERIFICATION_URL",
            )
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ConfigurationError(
                "Faltan variables obligatorias: " + ", ".join(sorted(missing))
            )
        if len(values["DTE_API_KEY"]) < 32:
            raise ConfigurationError("DTE_API_KEY debe contener al menos 32 caracteres")
        return cls(
            database_path=Path(values["DTE_DATABASE_PATH"]),
            tenant_id=values["DTE_TENANT_ID"],
            api_key=values["DTE_API_KEY"],
            caf_path=_existing_file(values["DTE_CAF_PATH"], "CAF"),
            sii_certificate_path=_existing_file(
                values["DTE_SII_CERTIFICATE_PATH"],
                "certificado SII",
            ),
            sii_certificate_sha256=values["DTE_SII_CERTIFICATE_SHA256"],
            pfx_path=_existing_file(values["DTE_PFX_PATH"], "PFX"),
            pfx_password=values["DTE_PFX_PASSWORD"],
            envio_boleta_xsd_path=_existing_file(
                values["DTE_ENVIO_BOLETA_XSD_PATH"],
                "XSD EnvioBOLETA",
            ),
            resolution_date=_parse_date(values["DTE_RESOLUTION_DATE"]),
            resolution_number=_parse_non_negative_int(
                values["DTE_RESOLUTION_NUMBER"],
                "DTE_RESOLUTION_NUMBER",
            ),
            verification_url=_parse_https_url(values["DTE_VERIFICATION_URL"]),
        )


def create_app_from_environment():
    settings = LocalSettings.from_environment()
    caf_untrusted = CafLoader().load(settings.caf_path.read_bytes())
    certificates = SiiCertificateStore()
    certificates.add(
        caf_untrusted.data.key_id,
        settings.sii_certificate_path.read_bytes(),
        expected_sha256=settings.sii_certificate_sha256,
    )
    caf = CafAuthenticityValidator(certificates).validate(caf_untrusted)
    credential = CertificateLoader().load(
        settings.pfx_path.read_bytes(),
        settings.pfx_password,
    )
    ledger = FolioLedger(settings.database_path)
    ledger.migrate()
    caf_id = ledger.import_caf(settings.tenant_id, caf)
    registry: dict[str, TrustedCafAuthorization] = {caf_id: caf}
    schema = XmlSchemaValidator(settings.envio_boleta_xsd_path)
    envelope_authorization = EnvelopeAuthorization(
        settings.resolution_date,
        settings.resolution_number,
    )

    def validate_signed_dte(document) -> None:
        envelope = EnvioBoletaBuilder().build(
            (document,),
            issuer_rut=caf.data.issuer_rut,
            sender_rut=caf.data.issuer_rut,
            authorization=envelope_authorization,
            signed_at=datetime.now(timezone.utc),
            credential=credential,
        )
        schema.validate(envelope.xml)

    issue_service = IssueBoletaService(
        ledger=ledger,
        resolve_caf=lambda requested: registry[requested],
        resolve_credential=lambda tenant_id, taxpayer_rut: _resolve_single_credential(
            tenant_id,
            taxpayer_rut,
            expected_tenant=settings.tenant_id,
            expected_rut=caf.data.issuer_rut,
            credential=credential,
        ),
        validate_signed_dte=validate_signed_dte,
    )
    return create_app(
        issue_service=issue_service,
        ledger=ledger,
        api_keys={settings.api_key: settings.tenant_id},
        resolve_receipt_config=lambda _tenant, _rut: ReceiptConfig(
            verification_url=settings.verification_url,
            resolution_number=settings.resolution_number,
            resolution_year=settings.resolution_date.year,
        ),
    )


def _existing_file(value: str, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ConfigurationError(f"La ruta de {label} no apunta a un archivo: {path}")
    return path


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigurationError("DTE_RESOLUTION_DATE debe usar AAAA-MM-DD") from exc


def _parse_non_negative_int(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigurationError(f"{label} debe ser un entero") from exc
    if parsed < 0:
        raise ConfigurationError(f"{label} no puede ser negativo")
    return parsed


def _parse_https_url(value: str) -> str:
    if not value.startswith("https://") or len(value) > 500:
        raise ConfigurationError("DTE_VERIFICATION_URL debe ser una URL HTTPS")
    return value.rstrip("/")


def _resolve_single_credential(
    tenant_id: str,
    taxpayer_rut: str,
    *,
    expected_tenant: str,
    expected_rut: str,
    credential,
):
    if tenant_id != expected_tenant or taxpayer_rut != expected_rut:
        raise ConfigurationError("No existe credencial para el tenant y RUT solicitados")
    return credential
