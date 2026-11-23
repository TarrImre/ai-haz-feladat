"""Az API egységes válaszburka: siker, keretrendszer-hiba, validáció, váratlan hiba."""
import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client():
    return TestClient(main.app, raise_server_exceptions=False)


def test_success_envelope(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "success", "message": "", "data": {"ok": True}}


def test_list_envelope_has_page_data(client):
    body = client.get("/api/invoices?page=1&page_size=5").json()
    assert body["status"] == "success"
    assert {"items", "total", "page", "pages", "page_size"} <= body["data"].keys()


def test_report_company_from_config(client):
    data = client.get("/api/report").json()["data"]
    assert data["company"] == {"name": "Nordwind Solutions Kft.", "tax_id": "26481937-2-43"}


def test_report_lists_failed_upload(client):
    client.post("/api/upload", files={"files": ("rossz.pdf", b"nem pdf", "application/pdf")})
    failed = client.get("/api/report").json()["data"]["failed_uploads"]
    assert failed[0]["filename"] == "rossz.pdf"
    assert failed[0]["status"] == "hiba"


def test_reset_message(client):
    body = client.delete("/api/data").json()
    assert body["status"] == "success"
    assert body["message"] == f"{body['data']['deleted']} számla törölve."


def test_validation_error_names_fields(client):
    res = client.get("/api/invoices?page=0&order=fel")
    assert res.status_code == 422
    assert res.json() == {"status": "error", "message": "Érvénytelen vagy hiányzó paraméter: order, page"}


def test_missing_upload_body(client):
    res = client.post("/api/upload")
    assert res.status_code == 422
    assert res.json()["message"] == "Érvénytelen vagy hiányzó paraméter: files"


def test_own_http_error_message(client):
    files = [("files", (f"{i}.pdf", b"x", "application/pdf")) for i in range(main.MAX_FILES_PER_REQUEST + 1)]
    res = client.post("/api/upload", files=files)
    assert res.status_code == 413
    assert res.json() == {"status": "error", "message": f"Egy kérésben legfeljebb {main.MAX_FILES_PER_REQUEST} fájl"}


def test_unknown_route_hungarian(client):
    res = client.get("/api/nincs-ilyen")
    assert res.status_code == 404
    assert res.json() == {"status": "error", "message": "Nincs ilyen végpont."}


def test_wrong_method_hungarian(client):
    res = client.get("/api/upload")
    assert res.status_code == 405
    assert res.json()["message"] == "A végpont ezt a metódust nem támogatja."


def test_unexpected_error_hides_details(client, monkeypatch):
    def boom(*_):
        raise RuntimeError("belső részlet")
    monkeypatch.setattr(main.store, "all_invoices", boom)
    res = client.get("/api/report")
    assert res.status_code == 500
    assert res.json() == {"status": "error", "message": "Váratlan szerverhiba történt."}
