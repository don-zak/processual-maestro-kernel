from fastapi.testclient import TestClient

from processual_api.auth import security
from processual_api.main import app


def test_admin_ui_jwt_authorizes_settings_api_keys_list(monkeypatch):
    def fake_verify_access_token(token: str) -> dict:
        assert token == "fake-admin-ui-token"
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
        "/settings/api-keys",
        headers={"Authorization": "Bearer fake-admin-ui-token"},
    )

    assert response.status_code == 200


def test_client_jwt_without_admin_scope_cannot_list_settings_api_keys(monkeypatch):
    def fake_verify_access_token(token: str) -> dict:
        assert token == "fake-client-ui-token"
        return {
            "sub": "client-user",
            "client_id": "client-user",
            "role": "client",
            "session_type": "ui_client",
            "scopes": ["evaluation"],
        }

    monkeypatch.setattr(security, "verify_access_token", fake_verify_access_token)

    client = TestClient(app)
    response = client.get(
        "/settings/api-keys",
        headers={"Authorization": "Bearer fake-client-ui-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing required scope: admin:settings"
