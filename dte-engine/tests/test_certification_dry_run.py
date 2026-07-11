from datetime import date, datetime, timezone
from decimal import Decimal
from html import escape

import httpx

from completo_dte.adapters.sii import SiiBoletaApi, SiiLegacyDteApi
from completo_dte.domain import (
    BoletaAfecta,
    BoletaLine,
    DailyFolio,
    DailySummaryBuilder,
    DteBuilder,
    EnvelopeAuthorization,
    EnvioBoletaBuilder,
    Issuer,
    TedBuilder,
    XmlSigner,
)
from completo_dte.infrastructure import AttemptState, EnvelopeState, FolioLedger
from factories import make_signing_credential, make_trusted_caf


def test_complete_five_folio_certification_dry_run(tmp_path) -> None:
    now = datetime(2026, 7, 9, 15, 30, tzinfo=timezone.utc)
    today = date(2026, 7, 9)
    issuer = Issuer(
        rut="12345678-5",
        legal_name="EMISOR SINTETICO SPA",
        business_activity="RESTAURANTES",
        activity_code=561000,
        address="CALLE UNO 123",
        commune="SANTIAGO",
    )
    cases = (
        (
            BoletaLine("Cambio de aceite", Decimal(1), Decimal(19900)),
            BoletaLine("Alineacion y balanceo", Decimal(1), Decimal(9900)),
        ),
        (BoletaLine("Papel de regalo", Decimal(17), Decimal(120)),),
        (
            BoletaLine("Sandwic", Decimal(2), Decimal(1500)),
            BoletaLine("Bebida", Decimal(2), Decimal(550)),
        ),
        (
            BoletaLine("item afecto 1", Decimal(8), Decimal(1590)),
            BoletaLine("item exento 2", Decimal(2), Decimal(1000), is_exempt=True),
        ),
        (BoletaLine("Arroz", Decimal(5), Decimal(700), unit_measure="Kg"),),
    )
    caf = make_trusted_caf(folio_from=1, folio_to=5)
    credential = make_signing_credential()
    documents = []
    daily = []
    for folio, lines in enumerate(cases, 1):
        boleta = BoletaAfecta(
            issuer=issuer,
            folio=folio,
            issued_on=today,
            lines=lines,
            reference_code="SET",
            reference_reason=f"CASO-{folio}",
        )
        ted = TedBuilder().build(boleta, caf, generated_at=now)
        unsigned = DteBuilder().build(boleta, ted, signed_at=now)
        signed = XmlSigner().sign(unsigned, credential)
        documents.append(signed)
        daily.append(
            DailyFolio(
                39,
                folio,
                today,
                boleta.net_total,
                boleta.vat_total,
                boleta.exempt_total,
                boleta.total,
            )
        )

    authorization = EnvelopeAuthorization(date(2026, 7, 1), 0)
    envelope = EnvioBoletaBuilder().build(
        tuple(documents),
        issuer_rut=issuer.rut,
        sender_rut=issuer.rut,
        authorization=authorization,
        signed_at=now,
        credential=credential,
        set_id="SET_CERT_5",
    )
    rcof = DailySummaryBuilder().build(
        tuple(daily),
        issuer_rut=issuer.rut,
        sender_rut=issuer.rut,
        authorization=authorization,
        sequence=1,
        signed_at=now,
        credential=credential,
        document_id="RCOF_CERT_5",
    )

    ledger = FolioLedger(tmp_path / "dry-run.sqlite3")
    ledger.migrate()
    env_record = ledger.persist_envelope(
        tenant_id="tenant-cert",
        taxpayer_rut=issuer.rut,
        kind="envio_boleta",
        document_id=envelope.set_id,
        signed_xml=envelope.xml,
    )
    rcof_record = ledger.persist_envelope(
        tenant_id="tenant-cert",
        taxpayer_rut=issuer.rut,
        kind="rcof",
        document_id=rcof.document_id,
        signed_xml=rcof.xml,
    )

    def soap(method: str, inner: str) -> bytes:
        return (
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
            f"<soapenv:Body><{method}Response><{method}Return>{escape(inner)}"
            f"</{method}Return></{method}Response></soapenv:Body></soapenv:Envelope>"
        ).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("boleta.electronica.semilla"):
            return httpx.Response(
                200, content=b"<R><SEMILLA>12345</SEMILLA><ESTADO>00</ESTADO></R>"
            )
        if path.endswith("boleta.electronica.token"):
            return httpx.Response(
                200, content=b"<R><TOKEN>rest-token</TOKEN><ESTADO>00</ESTADO></R>"
            )
        if request.url.host == "pangal.sii.cl":
            assert request.content.count(b"<DTE") == 5
            return httpx.Response(
                200,
                json={
                    "rut_emisor": issuer.rut,
                    "rut_envia": issuer.rut,
                    "trackid": 111,
                    "fecha_recepcion": "2026-07-09 12:00:00",
                    "estado": "REC",
                    "file": "set.xml",
                },
            )
        if path.endswith("/CrSeed.jws"):
            return httpx.Response(
                200,
                content=soap(
                    "getSeed",
                    "<R><ESTADO>00</ESTADO><SEMILLA>12345</SEMILLA></R>",
                ),
            )
        if path.endswith("/GetTokenFromSeed.jws"):
            return httpx.Response(
                200,
                content=soap(
                    "getToken",
                    "<R><ESTADO>00</ESTADO><TOKEN>legacy-token</TOKEN></R>",
                ),
            )
        assert b"<ConsumoFolios" in request.content
        return httpx.Response(
            200,
            content=b"<RECEPCIONDTE><STATUS>0</STATUS><TRACKID>222</TRACKID></RECEPCIONDTE>",
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    boleta_api = SiiBoletaApi(credential, client=client)
    legacy_api = SiiLegacyDteApi(credential, client=client)

    env_attempt = ledger.begin_submission(env_record.id)
    env_receipt = boleta_api.upload_boletas(
        envelope.xml,
        issuer_rut=issuer.rut,
        sender_rut=issuer.rut,
        filename="set.xml",
    )
    ledger.complete_submission(
        env_attempt.id, status=AttemptState.SUCCEEDED, track_id=env_receipt.track_id
    )

    rcof_attempt = ledger.begin_submission(rcof_record.id)
    rcof_receipt = legacy_api.upload(
        rcof.xml,
        issuer_rut=issuer.rut,
        sender_rut=issuer.rut,
        filename="rcof.xml",
    )
    ledger.complete_submission(
        rcof_attempt.id, status=AttemptState.SUCCEEDED, track_id=rcof_receipt.track_id
    )

    assert ledger.envelope_by_id(
        env_record.id, tenant_id="tenant-cert"
    ).status is EnvelopeState.SUBMITTED
    assert ledger.envelope_by_id(
        rcof_record.id, tenant_id="tenant-cert"
    ).status is EnvelopeState.SUBMITTED
