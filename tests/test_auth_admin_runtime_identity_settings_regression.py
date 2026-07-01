from fastapi.testclient import TestClient

from processual_api.auth import security
from processual_api.main import app


class FakeJWT:
    captured_payload = None
    captured_algorithm = None
    decoded_tokens = []
    decoded_algorithms = []

    @classmethod
    def encode(cls, payload, _secret, algorithm):
        cls.captured_payload = payload
        cls.captured_algorithm = algorithm
        return "fake.admin.runtime.jwt"

    @classmethod
    def decode(cls, token, _secret, algorithms=None):
        cls.decoded_tokens.append(token)
        cls.decoded_algorithms.append(algorithms)
        assert token == "fake.admin.runtime.jwt"
        assert cls.captured_payload is not None
        return cls.captured_payload


def test_admin_runtime_login_preserves_identity_and_settings_access(monkeypatch):
    FakeJWT.captured_payload = None
    FakeJWT.captured_algorithm = None
    FakeJWT.decoded_tokens = []
    FakeJWT.decoded_algorithms = []
    monkeypatch.setattr(security, "jwt", FakeJWT)

    client = TestClient(app)
    login_response = client.post(
        "/auth/token",
        json={
            "username": "admin",
            "password": "admin",
            "role": "admin",
        },
    )

    assert login_response.status_code == 200
    body = login_response.json()
    assert body["access_token"] == "fake.admin.runtime.jwt"
    assert body["token_type"] == "bearer"

    payload = FakeJWT.captured_payload

    assert payload is not None
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"
    assert payload["client_id"] == "admin"
    assert payload["session_type"] == "ui_admin"
    assert payload["scopes"] == ["*"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer " + body["access_token"]},
    )

    assert me_response.status_code == 200
    me_body = me_response.json()

    assert me_body["sub"] == "admin"
    assert me_body["user_id"] == "admin"
    assert me_body["client_id"] == "admin"
    assert me_body["role"] == "admin"
    assert me_body["auth_method"] == "jwt"
    assert me_body["session_type"] == "ui_admin"
    assert me_body["scopes"] == ["*"]

    settings_response = client.get(
        "/settings/api-keys",
        headers={"Authorization": "Bearer " + body["access_token"]},
    )

    assert settings_response.status_code == 200
    assert FakeJWT.decoded_tokens == [
        "fake.admin.runtime.jwt",
        "fake.admin.runtime.jwt",
    ]
