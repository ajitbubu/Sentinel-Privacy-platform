from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "pmp-backend"


def test_consent_requires_auth():
    resp = client.get("/api/v1/consent")
    assert resp.status_code == 403  # no bearer token
