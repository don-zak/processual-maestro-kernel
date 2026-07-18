from fastapi.testclient import TestClient

from processual_api.auth import security
from processual_api.main import app
from processual_api.settings import settings


def use_default_dev_credentials(monkeypatch):
    monkeypatch.setattr(settings, "maestro_admin_email", "")
    monkeypatch.setattr(settings, "maestro_admin_password", "")


class FakeJWT:
    captured_payload = None
    captured_algorithm = None
    decoded_token = None
    decoded_algorithms = None

    @classmethod
    def encode(cls, payload, _secret, algorithm):
        cls.captured_payload = payload
        cls.captured_algorithm = algorithm
        return "fake.client.me.jwt"

    @classmethod
    def decode(cls, token, _secret, algorithms=None):
        cls.decoded_token = token
        cls.decoded_algorithms = algorithms
        assert token == "fake.client.me.jwt"
        assert cls.captured_payload is not None
        return cls.captured_payload


def test_user_role_runtime_login_auth_me_remains_client_identity(monkeypatch):
    use_default_dev_credentials(monkeypatch)
    FakeJWT.captured_payload = None
    FakeJWT.captured_algorithm = None
    FakeJWT.decoded_token = None
    FakeJWT.decoded_algorithms = None
    monkeypatch.setattr(security, "jwt", FakeJWT)

    client = TestClient(app)
    login_response = client.post(
        "/auth/token",
        json={
            "username": "admin",
            "password": "admin",
            "role": "user",
        },
    )

    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    assert token == "fake.client.me.jwt"

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer " + token},
    )

    assert FakeJWT.decoded_token == "fake.client.me.jwt"
    assert me_response.status_code == 200

    body = me_response.json()

    assert body["sub"] == "admin"
    assert body["user_id"] == "admin"
    assert body["client_id"] == "admin"
    assert body["role"] == "client"
    assert body["auth_method"] == "jwt"
    assert body["session_type"] == "ui_client"
    assert body["scopes"] == ["evaluation"]

    assert body["role"] != "admin"
    assert body["session_type"] != "ui_admin"
    assert "*" not in body["scopes"]
    assert "admin:settings" not in body["scopes"]
