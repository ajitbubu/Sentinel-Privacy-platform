from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "idp-backend"


def test_banner_requires_auth():
    resp = client.get("/api/v1/banner")
    assert resp.status_code == 403
