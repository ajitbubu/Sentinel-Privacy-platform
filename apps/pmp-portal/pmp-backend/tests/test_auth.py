"""Magic-link auth tests. Redis-dependent tests are skipped when Redis is down."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_magic_link_request_returns_202():
    with patch("src.services.auth_service.request_magic_link") as mock_req:
        resp = client.post("/api/v1/auth/magic-link", json={"email": "user@example.com"})
    assert resp.status_code == 202
    mock_req.assert_called_once_with("user@example.com")
    # Response must not reveal whether the account exists
    assert "valid" in resp.json()["message"].lower()


def test_magic_link_rejects_bad_email():
    resp = client.post("/api/v1/auth/magic-link", json={"email": "not-an-email"})
    assert resp.status_code == 422


def test_verify_rejects_invalid_token():
    with patch("src.services.auth_service.verify_magic_link", return_value=None):
        resp = client.post("/api/v1/auth/verify", json={"token": "bogus"})
    assert resp.status_code == 401


def test_verify_issues_tokens():
    with patch("src.services.auth_service.verify_magic_link",
               return_value=("subject-uuid", "user@example.com")), \
         patch("src.services.auth_service.store_refresh_token", return_value="refresh-abc"):
        resp = client.post("/api/v1/auth/verify", json={"token": "good-token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "Bearer"
    assert body["refresh_token"] == "refresh-abc"
    assert body["access_token"]


def test_refresh_rejects_invalid_token():
    with patch("src.services.auth_service.rotate_refresh_token", return_value=None):
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "bogus"})
    assert resp.status_code == 401
