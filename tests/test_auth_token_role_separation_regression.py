from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.auth import security
from processual_api.main import app
from processual_api.settings import settings

ROOT = Path(__file__).resolve().parents[1]


def use_default_dev_credentials(monkeypatch):
    monkeypatch.setattr(settings, "maestro_admin_email", "")
    monkeypatch.setattr(settings, "maestro_admin_password", "")


class FakeJWT:
    captured_payload = None
    captured_algorithm = None

    @classmethod
    def encode(cls, payload, _secret, algorithm):
        cls.captured_payload = payload
        cls.captured_algorithm = algorithm
        return "fake.role.jwt"


def test_auth_token_runtime_issues_client_ui_claims_for_user_role(monkeypatch):
    use_default_dev_credentials(monkeypatch)
    FakeJWT.captured_payload = None
    monkeypatch.setattr(security, "jwt", FakeJWT)

    client = TestClient(app)
    response = client.post(
        "/auth/token",
        json={
            "username": "admin",
            "password": "admin",
            "role": "user",
        },
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "fake.role.jwt"

    payload = FakeJWT.captured_payload

    assert payload is not None
    assert payload["sub"] == "admin"
    assert payload["role"] == "client"
    assert payload["client_id"] == "admin"
    assert payload["session_type"] == "ui_client"
    assert payload["scopes"] == ["evaluation"]


def test_auth_token_rejects_unknown_login_role(monkeypatch):
    use_default_dev_credentials(monkeypatch)
    client = TestClient(app)
    response = client.post(
        "/auth/token",
        json={
            "username": "admin",
            "password": "admin",
            "role": "owner",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid login role"


def test_login_page_sends_selected_role_to_auth_token():
    source = (ROOT / "processual_api" / "static" / "login.html").read_text(
        encoding="utf-8"
    )

    assert "role: currentRole" in source
