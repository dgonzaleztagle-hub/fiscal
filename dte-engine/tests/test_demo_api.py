from fastapi.testclient import TestClient

from completo_dte.api.demo import DEMO_TOKEN, create_demo_app


def test_demo_api_is_seeded_and_keeps_real_material_out(tmp_path) -> None:
    app = create_demo_app(database_path=tmp_path / "demo.sqlite3")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {DEMO_TOKEN}"}

    assert app.state.fiscal_environment == "demo"
    assert app.state.synthetic_material is True
    documents = client.get("/v1/fiscal-documents", headers=headers)
    assert documents.status_code == 200
    assert {item["document_type"] for item in documents.json()} == {39, 41}

    record_id = documents.json()[0]["id"]
    assert client.get(f"/v1/fiscal-documents/{record_id}", headers=headers).status_code == 200
    assert client.get(f"/v1/fiscal-documents/{record_id}/xml", headers=headers).content.startswith(b"<?xml")
    assert client.get(f"/v1/fiscal-documents/{record_id}/pdf", headers=headers).content.startswith(b"%PDF-")
    assert client.get(f"/v1/fiscal-documents/{record_id}/events", headers=headers).json()


def test_demo_api_rejects_unknown_token(tmp_path) -> None:
    client = TestClient(create_demo_app(database_path=tmp_path / "demo.sqlite3"))
    response = client.get(
        "/v1/fiscal-documents",
        headers={"Authorization": "Bearer not-the-demo-token"},
    )
    assert response.status_code == 401
