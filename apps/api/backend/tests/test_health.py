from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "external-api"


def test_consent_requires_api_key():
    resp = client.post("/api/v1/consent", json={})
    assert resp.status_code == 403
