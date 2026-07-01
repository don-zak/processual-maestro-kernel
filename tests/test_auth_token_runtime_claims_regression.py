from fastapi.testclient import TestClient

from processual_api.auth import security
from processual_api.main import app


class FakeJWT:
    captured_payload = None
    captured_algorithm = None

    @classmethod
    def encode(cls, payload, _secret, algorithm):
        cls.captured_payload = payload
        cls.captured_algorithm = algorithm
        return "fake.runtime.jwt"


def test_auth_token_runtime_issues_admin_ui_jwt_claims(monkeypatch):
    FakeJWT.captured_payload = None
    FakeJWT.captured_algorithm = None
    monkeypatch.setattr(security, "jwt", FakeJWT)

    client = TestClient(app)
    response = client.post(
        "/auth/token",
        json={
            "username": "admin",
            "password": "admin",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["access_token"] == "fake.runtime.jwt"
    assert body["token_type"] == "bearer"

    payload = FakeJWT.captured_payload

    assert payload is not None
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"
    assert payload["client_id"] == "admin"
    assert payload["session_type"] == "ui_admin"
    assert payload["scopes"] == ["*"]
    assert "exp" in payload
    assert "iat" in payload
