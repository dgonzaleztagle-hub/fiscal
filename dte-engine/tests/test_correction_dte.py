from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from completo_dte.domain import (
    CorrectionCode,
    CorrectionDocument,
    CorrectionDteBuilder,
    CorrectionReference,
    DocumentType,
    FiscalLine,
    Issuer,
    Party,
    PriceMode,
    TaxCategory,
    TedBuilder,
    XmlSchemaValidator,
    XmlSigner,
)
from factories import make_signing_credential, make_trusted_caf
from test_official_invoice_schema import schema


def correction(document_type=DocumentType.NOTA_CREDITO):
    return CorrectionDocument(
        issuer=Issuer(
            rut="12345678-5",
            legal_name="SOFTWARE SINTETICO SPA",
            business_activity="DESARROLLO DE SOFTWARE",
            activity_code=620100,
            address="AVENIDA UNO 100",
            commune="SANTIAGO",
        ),
        receiver=Party(
            rut="11111111-1",
            legal_name="CLIENTE SINTETICO SPA",
            business_activity="SERVICIOS EMPRESARIALES",
            address="CALLE DOS 200",
            commune="PROVIDENCIA",
            email="facturas@example.test",
        ),
        document_type=document_type,
        folio=1,
        issued_on=date(2026, 7, 11),
        lines=(
            FiscalLine(
                name="Diferencia servicio mensual",
                quantity=Decimal(1),
                unit_price=Decimal(1000),
                tax_category=TaxCategory.AFFECTED,
                price_mode=PriceMode.NET,
            ),
        ),
        reference=CorrectionReference(
            document_type=DocumentType.FACTURA_AFECTA,
            folio=7,
            issued_on=date(2026, 7, 10),
            code=CorrectionCode.FIX_AMOUNT,
            reason="Diferencia en precio informado",
        ),
    )


@pytest.mark.parametrize(
    "document_type",
    [DocumentType.NOTA_CREDITO, DocumentType.NOTA_DEBITO],
)
def test_amount_correction_56_61_signs_and_validates_official_xsd(document_type) -> None:
    note = correction(document_type)
    timestamp = datetime(2026, 7, 11, 15, 30, tzinfo=timezone.utc)
    ted = TedBuilder().build(
        note,
        make_trusted_caf(document_type=int(document_type)),
        generated_at=timestamp,
    )
    signed = XmlSigner().sign(
        CorrectionDteBuilder().build(note, ted, signed_at=timestamp),
        make_signing_credential(),
    )

    XmlSchemaValidator(schema("DTE_v10.xsd")).validate(signed.xml)
    assert b"<CodRef>3</CodRef>" in signed.xml
    assert b"<MntTotal>1190</MntTotal>" in signed.xml


def test_text_correction_is_zero_value_and_validates_official_xsd() -> None:
    base = correction()
    text_line = FiscalLine(
        name="CORRIGE GIRO Y DIRECCION",
        quantity=Decimal(1),
        unit_price=Decimal(0),
        tax_category=TaxCategory.AFFECTED,
        price_mode=PriceMode.NET,
    )
    note = CorrectionDocument(
        **{
            **base.__dict__,
            "lines": (text_line,),
            "receiver": Party(
                **{
                    **base.receiver.__dict__,
                    "business_activity": "GIRO CORREGIDO",
                    "address": "DIRECCION CORREGIDA",
                }
            ),
            "reference": CorrectionReference(
                document_type=DocumentType.FACTURA_AFECTA,
                folio=7,
                issued_on=date(2026, 7, 10),
                code=CorrectionCode.FIX_TEXT,
                reason="CORRIGE TEXTO",
            ),
        }
    )
    timestamp = datetime(2026, 7, 11, 15, 30, tzinfo=timezone.utc)
    ted = TedBuilder().build(
        note,
        make_trusted_caf(document_type=61),
        generated_at=timestamp,
    )
    signed = XmlSigner().sign(
        CorrectionDteBuilder().build(note, ted, signed_at=timestamp),
        make_signing_credential(),
    )

    XmlSchemaValidator(schema("DTE_v10.xsd")).validate(signed.xml)
    assert b"<CodRef>2</CodRef>" in signed.xml
    assert b"<MntTotal>0</MntTotal>" in signed.xml
    assert b"<PrcItem>" not in signed.xml


def test_annulment_61_copies_amounts_and_validates_official_xsd() -> None:
    note = correction()
    note = CorrectionDocument(
        **{
            **note.__dict__,
            "reference": CorrectionReference(
                document_type=DocumentType.FACTURA_AFECTA,
                folio=7,
                issued_on=date(2026, 7, 10),
                code=CorrectionCode.VOID,
                reason="ANULA DOCUMENTO DE REFERENCIA",
            ),
        }
    )
    timestamp = datetime(2026, 7, 11, 15, 30, tzinfo=timezone.utc)
    ted = TedBuilder().build(
        note,
        make_trusted_caf(document_type=61),
        generated_at=timestamp,
    )
    signed = XmlSigner().sign(
        CorrectionDteBuilder().build(note, ted, signed_at=timestamp),
        make_signing_credential(),
    )

    XmlSchemaValidator(schema("DTE_v10.xsd")).validate(signed.xml)
    assert b"<CodRef>1</CodRef>" in signed.xml
