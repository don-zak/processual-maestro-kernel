from fastapi.testclient import TestClient

from processual_api.auth import security
from processual_api.main import app
from processual_api.settings import settings

ADMIN_EMAIL = "maestro-root-zak@internal.local"
ADMIN_PASSWORD = "test-strong-admin-password-12345"


class FakeJWT:
    captured_payloads = []
    captured_algorithm = None

    @classmethod
    def encode(cls, payload, _secret, algorithm):
        cls.captured_payloads.append(payload)
        cls.captured_algorithm = algorithm
        return "fake.creds.jwt"


def configure_admin_credentials(monkeypatch):
    monkeypatch.setattr(settings, "maestro_admin_email", ADMIN_EMAIL)
    monkeypatch.setattr(settings, "maestro_admin_password", ADMIN_PASSWORD)


def reset_fake_jwt():
    FakeJWT.captured_payloads = []
    FakeJWT.captured_algorithm = None


def test_configured_admin_email_password_issues_admin_ui_jwt(monkeypatch):
    reset_fake_jwt()
    configure_admin_credentials(monkeypatch)
    monkeypatch.setattr(security, "jwt", FakeJWT)

    client = TestClient(app)
    response = client.post(
        "/auth/token",
        json={
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "role": "admin",
        },
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "fake.creds.jwt"

    payload = FakeJWT.captured_payloads[-1]

    assert payload["sub"] == ADMIN_EMAIL
    assert payload["role"] == "admin"
    assert payload["client_id"] == "admin"
    assert payload["session_type"] == "ui_admin"
    assert payload["scopes"] == ["*"]


def test_configured_admin_email_password_can_issue_client_ui_jwt(monkeypatch):
    reset_fake_jwt()
    configure_admin_credentials(monkeypatch)
    monkeypatch.setattr(security, "jwt", FakeJWT)

    client = TestClient(app)
    response = client.post(
        "/auth/token",
        json={
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "role": "user",
        },
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "fake.creds.jwt"

    payload = FakeJWT.captured_payloads[-1]

    assert payload["sub"] == ADMIN_EMAIL
    assert payload["role"] == "client"
    assert payload["client_id"] == ADMIN_EMAIL
    assert payload["session_type"] == "ui_client"
    assert payload["scopes"] == ["evaluation"]


def test_configured_admin_email_password_rejects_wrong_password(monkeypatch):
    configure_admin_credentials(monkeypatch)

    client = TestClient(app)
    response = client.post(
        "/auth/token",
        json={
            "username": ADMIN_EMAIL,
            "password": "wrong-password",
            "role": "admin",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_configured_admin_email_password_rejects_wrong_email(monkeypatch):
    configure_admin_credentials(monkeypatch)

    client = TestClient(app)
    response = client.post(
        "/auth/token",
        json={
            "username": "wrong-admin@internal.local",
            "password": ADMIN_PASSWORD,
            "role": "admin",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"
