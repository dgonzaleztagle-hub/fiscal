"""Aplicación local demostrativa con material criptográfico efímero y sintético."""

from __future__ import annotations

import base64
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import re
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from completo_dte.application import IssueBoletaCommand, IssueBoletaService
from completo_dte.domain import (
    BoletaLine,
    CafAuthenticityValidator,
    CafLoader,
    Issuer,
    SiiCertificateStore,
    SigningCredential,
)
from completo_dte.infrastructure import FolioLedger
from completo_dte.presentation import ReceiptConfig

from .app import create_app

DEMO_TENANT = "tenant-demo-fiscal"
DEMO_TOKEN = "completo-fiscal-demo-local-token-only"  # noqa: S105 - entorno local sintético.
DEMO_ISSUER_RUT = "12345678-5"


def create_demo_app(*, database_path: Path | None = None):
    """Crea y siembra una API que jamás carga CAF, PFX ni endpoints reales."""
    if database_path is None:
        database_path = Path(tempfile.mkdtemp(prefix="completo-fiscal-demo-")) / "demo.sqlite3"
    ledger = FolioLedger(database_path)
    ledger.migrate()
    credential = _signing_credential()
    cafs = {}
    for document_type in (39, 41):
        caf = _trusted_caf(document_type=document_type)
        cafs[ledger.import_caf(DEMO_TENANT, caf)] = caf

    service = IssueBoletaService(
        ledger=ledger,
        resolve_caf=lambda caf_id: cafs[caf_id],
        resolve_credential=lambda _tenant, _rut: credential,
        validate_signed_dte=lambda _document: None,
        clock=lambda: datetime(2026, 7, 11, 12, 30, tzinfo=timezone.utc),
    )
    issuer = Issuer(
        rut=DEMO_ISSUER_RUT,
        legal_name="EMPRESA SINTETICA COMPLETO SPA",
        business_activity="SERVICIOS DE DEMOSTRACION",
        activity_code=620200,
        address="CALLE DEMO 123",
        commune="SANTIAGO",
    )
    service.issue(
        IssueBoletaCommand(
            tenant_id=DEMO_TENANT,
            idempotency_key="seed-boleta-afecta",
            issuer=issuer,
            issued_on=date(2026, 7, 11),
            lines=(BoletaLine("Venta demostrativa", Decimal(2), Decimal(5990)),),
            document_type=39,
        )
    )
    service.issue(
        IssueBoletaCommand(
            tenant_id=DEMO_TENANT,
            idempotency_key="seed-boleta-exenta",
            issuer=issuer,
            issued_on=date(2026, 7, 11),
            lines=(
                BoletaLine(
                    "Servicio exento demostrativo",
                    Decimal(1),
                    Decimal(15000),
                    is_exempt=True,
                ),
            ),
            document_type=41,
        )
    )
    app = create_app(
        issue_service=service,
        ledger=ledger,
        api_keys={DEMO_TOKEN: DEMO_TENANT},
        resolve_receipt_config=lambda _tenant, _rut: ReceiptConfig(
            verification_url="https://demo.invalid/documentos",
            resolution_number=0,
            resolution_year=2026,
        ),
    )
    app.state.fiscal_environment = "demo"
    app.state.synthetic_material = True
    return app


def _signing_credential(*, key_size: int = 2048) -> SigningCredential:
    key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "COMPLETO DEMO SINTETICO")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return SigningCredential(certificate=certificate, private_key=key)


def _trusted_caf(*, document_type: int):
    sii = _signing_credential(key_size=1024)
    payload = _synthetic_caf(document_type=document_type, sii_key=sii.private_key)
    store = SiiCertificateStore()
    store.add(100 + document_type, sii.certificate.public_bytes(serialization.Encoding.DER))
    return CafAuthenticityValidator(store).validate(CafLoader().load(payload))


def _synthetic_caf(*, document_type: int, sii_key: rsa.RSAPrivateKey) -> bytes:
    # Replica el tamaño de clave fijado por el formato CAF del SII; sólo genera datos sintéticos.
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)  # noqa: S505
    numbers = key.public_key().public_numbers()
    modulus = base64.b64encode(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")).decode()
    exponent = base64.b64encode(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")).decode()
    private = base64.b64encode(
        key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    ).decode()
    key_id = 100 + document_type
    caf = (
        f'<CAF version="1.0"><DA><RE>{DEMO_ISSUER_RUT}</RE>'
        f"<RS>EMPRESA SINTETICA COMPLETO SPA</RS><TD>{document_type}</TD>"
        f"<RNG><D>1</D><H>100</H></RNG><FA>2026-07-11</FA>"
        f"<RSAPK><M>{modulus}</M><E>{exponent}</E></RSAPK><IDK>{key_id}</IDK></DA>"
    )
    da = etree.fromstring((caf + "</CAF>").encode("ascii")).find("DA")
    canonical = etree.tostring(da, method="c14n", exclusive=False, with_comments=False)
    canonical = re.sub(rb">\s+<", b"><", canonical.decode().encode("iso-8859-1"))
    signature = sii_key.sign(canonical, padding.PKCS1v15(), hashes.SHA1())  # noqa: S303
    return (
        '<?xml version="1.0" encoding="ISO-8859-1"?><AUTORIZACION>'
        f'{caf}<FRMA algoritmo="SHA1withRSA">{base64.b64encode(signature).decode()}</FRMA>'
        f"</CAF><RSASK>{private}</RSASK></AUTORIZACION>"
    ).encode("ascii")
