from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import Encoding, pkcs12
from fastapi.testclient import TestClient
import pytest

from completo_dte.api.bootstrap import (
    ConfigurationError,
    LocalSettings,
    create_app_from_environment,
)
from factories import make_signing_credential, make_synthetic_caf


REQUIRED = (
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


def test_configuration_fails_closed_when_secrets_are_missing(monkeypatch) -> None:
    for name in REQUIRED:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigurationError, match="Faltan variables"):
        LocalSettings.from_environment()


def test_bootstrap_loads_real_files_without_hardcoded_secrets(tmp_path, monkeypatch) -> None:
    sii = make_signing_credential()
    emitter = make_signing_credential()
    caf_path = tmp_path / "caf.xml"
    sii_path = tmp_path / "sii.cer"
    pfx_path = tmp_path / "emitter.pfx"
    xsd_path = tmp_path / "EnvioBOLETA-test.xsd"
    caf_path.write_bytes(make_synthetic_caf(sii_signing_key=sii.private_key))
    sii_path.write_bytes(sii.certificate.public_bytes(Encoding.DER))
    pfx_path.write_bytes(
        pkcs12.serialize_key_and_certificates(
            b"emitter",
            emitter.private_key,
            emitter.certificate,
            None,
            serialization.BestAvailableEncryption(b"test-password"),
        )
    )
    xsd_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
 targetNamespace="http://www.sii.cl/SiiDte"
 xmlns:sii="http://www.sii.cl/SiiDte" elementFormDefault="qualified">
  <xs:element name="EnvioBOLETA">
    <xs:complexType>
      <xs:sequence><xs:any minOccurs="0" maxOccurs="unbounded" processContents="skip"/></xs:sequence>
      <xs:anyAttribute processContents="skip"/>
    </xs:complexType>
  </xs:element>
</xs:schema>""",
        encoding="utf-8",
    )
    environment = {
        "DTE_DATABASE_PATH": str(tmp_path / "api.sqlite3"),
        "DTE_TENANT_ID": "tenant-a",
        "DTE_API_KEY": "a-secure-local-test-token-with-32-chars",
        "DTE_CAF_PATH": str(caf_path),
        "DTE_SII_CERTIFICATE_PATH": str(sii_path),
        "DTE_SII_CERTIFICATE_SHA256": sii.certificate.fingerprint(hashes.SHA256()).hex(),
        "DTE_PFX_PATH": str(pfx_path),
        "DTE_PFX_PASSWORD": "test-password",
        "DTE_ENVIO_BOLETA_XSD_PATH": str(xsd_path),
        "DTE_RESOLUTION_DATE": "2026-07-01",
        "DTE_RESOLUTION_NUMBER": "0",
        "DTE_VERIFICATION_URL": "https://boletas.example.test",
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    client = TestClient(create_app_from_environment())
    assert client.get("/health").status_code == 200
