from html import escape

import httpx

from completo_dte.adapters.sii import EnvelopeOutcome, SiiLegacyDteApi
from factories import make_signing_credential


def _soap_return(method: str, inner: str) -> bytes:
    return (
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
        f"<soapenv:Body><{method}Response><{method}Return>"
        f"{escape(inner)}</{method}Return></{method}Response></soapenv:Body>"
        "</soapenv:Envelope>"
    ).encode()


def test_legacy_authentication_and_rcof_upload() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/CrSeed.jws"):
            return httpx.Response(
                200,
                content=_soap_return(
                    "getSeed",
                    "<RESPUESTA><RESP_HDR><ESTADO>00</ESTADO></RESP_HDR>"
                    "<RESP_BODY><SEMILLA>12345</SEMILLA></RESP_BODY></RESPUESTA>",
                ),
            )
        if request.url.path.endswith("/GetTokenFromSeed.jws"):
            assert b"pszXml" in request.content
            assert b"Signature" in request.content
            return httpx.Response(
                200,
                content=_soap_return(
                    "getToken",
                    "<RESPUESTA><RESP_HDR><ESTADO>00</ESTADO></RESP_HDR>"
                    "<RESP_BODY><TOKEN>legacy-token</TOKEN></RESP_BODY></RESPUESTA>",
                ),
            )
        assert request.headers["cookie"] == "TOKEN=legacy-token"
        assert b"<ConsumoFolios" in request.content
        return httpx.Response(
            200,
            content=(
                b"<RECEPCIONDTE><STATUS>0</STATUS><TRACKID>456789</TRACKID>"
                b"<TMST>2026-07-09 11:00:00</TMST></RECEPCIONDTE>"
            ),
        )

    api = SiiLegacyDteApi(
        make_signing_credential(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    receipt = api.upload(
        b"<ConsumoFolios/>",
        issuer_rut="12345678-5",
        sender_rut="12691078-9",
        filename="rcof.xml",
    )

    assert receipt.track_id == "456789"
    assert len(calls) == 3


def test_queries_and_classifies_rcof_upload_status() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/CrSeed.jws"):
            return httpx.Response(
                200,
                content=_soap_return(
                    "getSeed", "<R><ESTADO>00</ESTADO><SEMILLA>1</SEMILLA></R>"
                ),
            )
        if request.url.path.endswith("/GetTokenFromSeed.jws"):
            return httpx.Response(
                200,
                content=_soap_return(
                    "getToken", "<R><ESTADO>00</ESTADO><TOKEN>token</TOKEN></R>"
                ),
            )
        assert request.url.path.endswith("/QueryEstUp.jws")
        assert all(
            field in request.content
            for field in (b"RutCompania", b"DvCompania", b"TrackId", b"Token")
        )
        return httpx.Response(
            200,
            content=_soap_return(
                "getEstUp",
                "<RESPUESTA><RESP_HDR><ESTADO>EPR</ESTADO><TRACKID>456789</TRACKID>"
                "</RESP_HDR><RESP_BODY><TIPO_DOCTO>39</TIPO_DOCTO>"
                "<INFORMADOS>5</INFORMADOS><ACEPTADOS>5</ACEPTADOS>"
                "<RECHAZADOS>0</RECHAZADOS><REPAROS>0</REPAROS>"
                "</RESP_BODY></RESPUESTA>",
            ),
        )

    api = SiiLegacyDteApi(
        make_signing_credential(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    status = api.get_upload_status(issuer_rut="12345678-5", track_id="456789")

    assert status.reported == status.accepted == 5
    assert status.outcome is EnvelopeOutcome.ACCEPTED
    assert len(calls) == 3
