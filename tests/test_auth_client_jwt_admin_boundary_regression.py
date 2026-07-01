from fastapi.testclient import TestClient

from processual_api.auth import security
from processual_api.main import app


class FakeJWT:
    captured_payload = None
    captured_algorithm = None
    decoded_token = None
    decoded_algorithms = None

    @classmethod
    def encode(cls, payload, _secret, algorithm):
        cls.captured_payload = payload
        cls.captured_algorithm = algorithm
        return "fake.client.runtime.jwt"

    @classmethod
    def decode(cls, token, _secret, algorithms=None):
        cls.decoded_token = token
        cls.decoded_algorithms = algorithms
        assert token == "fake.client.runtime.jwt"
        assert cls.captured_payload is not None
        return cls.captured_payload


def test_user_role_runtime_login_jwt_cannot_access_admin_settings(monkeypatch):
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
    body = login_response.json()
    assert body["access_token"] == "fake.client.runtime.jwt"
    assert body["token_type"] == "bearer"

    payload = FakeJWT.captured_payload

    assert payload is not None
    assert payload["sub"] == "admin"
    assert payload["role"] == "client"
    assert payload["client_id"] == "admin"
    assert payload["session_type"] == "ui_client"
    assert payload["scopes"] == ["evaluation"]

    settings_response = client.get(
        "/settings/api-keys",
        headers={"Authorization": "Bearer " + body["access_token"]},
    )

    assert FakeJWT.decoded_token == "fake.client.runtime.jwt"
    assert settings_response.status_code == 403
    assert settings_response.json()["detail"] == "Missing required scope: admin:settings"
