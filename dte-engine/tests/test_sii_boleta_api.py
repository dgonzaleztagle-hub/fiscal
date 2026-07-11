import base64
import hashlib

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree

from completo_dte.adapters.sii import (
    EnvelopeOutcome,
    SeedSigner,
    SiiApiError,
    SiiBoletaApi,
    classify_envelope_status,
)
from completo_dte.domain.xml_signature import DS
from factories import make_signing_credential


def test_seed_signature_has_valid_digest_and_signature() -> None:
    credential = make_signing_credential()
    payload = SeedSigner().sign("1234567890", credential)
    root = etree.fromstring(payload)
    signature = root.find(f"{{{DS}}}Signature")
    assert signature is not None

    digest_value = signature.findtext(
        f"{{{DS}}}SignedInfo/{{{DS}}}Reference/{{{DS}}}DigestValue"
    )
    root.remove(signature)
    expected_digest = hashlib.sha1(
        etree.tostring(root, method="c14n", exclusive=False, with_comments=False)
    ).digest()
    assert base64.b64decode(digest_value) == expected_digest

    signed_info = signature.find(f"{{{DS}}}SignedInfo")
    signature_value = signature.findtext(f"{{{DS}}}SignatureValue")
    credential.certificate.public_key().verify(
        base64.b64decode(signature_value),
        etree.tostring(signed_info, method="c14n", exclusive=False, with_comments=False),
        padding.PKCS1v15(),
        hashes.SHA1(),
    )


def test_authenticate_upload_and_query_status_with_token_cache() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("semilla"):
            return httpx.Response(
                200,
                content=b"<RESPUESTA><SEMILLA>12345</SEMILLA><ESTADO>00</ESTADO></RESPUESTA>",
            )
        if request.url.path.endswith("token"):
            assert b"<Semilla>12345</Semilla>" in request.content
            return httpx.Response(
                200,
                content=b"<RESPUESTA><TOKEN>token-prueba</TOKEN><ESTADO>00</ESTADO></RESPUESTA>",
            )
        if request.method == "POST":
            assert request.headers["cookie"] == "TOKEN=token-prueba"
            body = request.content
            assert b'name="rutCompany"' in body
            assert b"12345678" in body
            assert b"<EnvioBOLETA" in body
            return httpx.Response(
                200,
                json={
                    "rut_emisor": "12345678-5",
                    "rut_envia": "12691078-9",
                    "trackid": 987654,
                    "fecha_recepcion": "2026-07-09 09:00:00",
                    "estado": "REC",
                    "file": "set-boletas.xml",
                },
            )
        assert request.headers["cookie"] == "TOKEN=token-prueba"
        return httpx.Response(
            200,
            json={
                "rut_emisor": "12345678-5",
                "rut_envia": "12691078-9",
                "trackid": 987654,
                "fecha_recepcion": "2026-07-09 09:00:00",
                "estado": "EPR",
                "estadistica": [{"tipo": 39, "informados": 5, "aceptados": 5}],
                "detalle_rep_rech": [],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    api = SiiBoletaApi(make_signing_credential(), client=client)

    receipt = api.upload_boletas(
        b"<EnvioBOLETA/>",
        issuer_rut="12.345.678-5",
        sender_rut="12.691.078-9",
        filename="set-boletas.xml",
    )
    status = api.get_envelope_status(issuer_rut="12345678-5", track_id=receipt.track_id)

    assert receipt.track_id == "987654"
    assert status.status == "EPR"
    assert status.outcome is EnvelopeOutcome.ACCEPTED
    assert status.statistics[0]["aceptados"] == 5
    assert sum(request.url.path.endswith("semilla") for request in calls) == 1
    assert sum(request.url.path.endswith("token") for request in calls) == 1


def test_sii_statuses_are_classified_conservatively() -> None:
    assert classify_envelope_status("REC") is EnvelopeOutcome.PROCESSING
    assert classify_envelope_status("RFR") is EnvelopeOutcome.REJECTED
    assert classify_envelope_status("RPR") is EnvelopeOutcome.ACCEPTED_WITH_OBJECTIONS
    assert classify_envelope_status("EPR") is EnvelopeOutcome.ACCEPTED
    assert classify_envelope_status(
        "EPR", ({"reparos": 1},)
    ) is EnvelopeOutcome.ACCEPTED_WITH_OBJECTIONS
    assert classify_envelope_status(
        "EPR", ({"rechazados": 1},)
    ) is EnvelopeOutcome.REJECTED
    assert classify_envelope_status("CODIGO-NUEVO") is EnvelopeOutcome.UNKNOWN


def test_status_query_rejects_invalid_track_id_before_network() -> None:
    api = SiiBoletaApi(
        make_signing_credential(),
        client=httpx.Client(transport=httpx.MockTransport(lambda _request: pytest.fail())),
    )
    with pytest.raises(SiiApiError, match="track_id"):
        api.get_envelope_status(issuer_rut="12345678-5", track_id="../otro")


def test_upload_rejects_uncorrelated_sii_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("semilla"):
            return httpx.Response(200, content=b"<R><SEMILLA>1</SEMILLA><ESTADO>00</ESTADO></R>")
        if request.url.path.endswith("token"):
            return httpx.Response(200, content=b"<R><TOKEN>token</TOKEN><ESTADO>00</ESTADO></R>")
        return httpx.Response(
            200,
            json={
                "rut_emisor": "11111111-1",
                "rut_envia": "12691078-9",
                "trackid": 1,
                "fecha_recepcion": "2026-07-09 09:00:00",
                "estado": "REC",
                "file": "set.xml",
            },
        )

    api = SiiBoletaApi(
        make_signing_credential(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(SiiApiError, match="no corresponde"):
        api.upload_boletas(
            b"<EnvioBOLETA/>",
            issuer_rut="12345678-5",
            sender_rut="12691078-9",
            filename="set.xml",
        )
