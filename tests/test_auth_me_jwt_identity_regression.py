from fastapi.testclient import TestClient

from processual_api.auth import security
from processual_api.main import app


def test_auth_me_returns_normalized_ui_jwt_identity(monkeypatch):
    def fake_verify_access_token(token: str) -> dict:
        assert token == "fake-ui-admin-token"
        return {
            "sub": "admin",
            "client_id": "admin",
            "role": "admin",
            "session_type": "ui_admin",
            "scopes": ["*"],
        }

    monkeypatch.setattr(security, "verify_access_token", fake_verify_access_token)

    client = TestClient(app)
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer fake-ui-admin-token"},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["sub"] == "admin"
    assert body["user_id"] == "admin"
    assert body["client_id"] == "admin"
    assert body["role"] == "admin"
    assert body["auth_method"] == "jwt"
    assert body["session_type"] == "ui_admin"
    assert body["scopes"] == ["*"]
