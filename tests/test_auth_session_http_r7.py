from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.auth.rate_limit import TrustedProxyPolicy
from processual_api.auth.session_contracts import IssuedSession, SessionView
from processual_api.auth.session_router import get_identity_user, get_session_runtime, router
from processual_api.auth.session_runtime import SessionRuntime


class AllowingLimiter:
    def __init__(self) -> None:
        self.calls = []

    async def consume(self, **values):
        self.calls.append(values)
        return SimpleNamespace(allowed=True, retry_after_seconds=0, remaining=10)


class FakeSessionService:
    def __init__(self) -> None:
        self.login_calls = []
        self.refresh_calls = []
        self.logout_calls = []

    @staticmethod
    def issued(suffix="one"):
        return IssuedSession(
            access_token=f"access-{suffix}",
            access_expires_in=900,
            refresh_token=f"refresh-{suffix}",
            refresh_expires_in=3600,
            csrf_token=f"csrf-{suffix}",
            session_id=uuid.uuid4(),
        )

    async def login(self, **values):
        self.login_calls.append(values)
        return self.issued()

    async def refresh(self, raw_token):
        self.refresh_calls.append(raw_token)
        return self.issued("two")

    async def logout(self, raw_token):
        self.logout_calls.append(raw_token)

    async def logout_all(self, raw_token):
        self.logout_calls.append(f"all:{raw_token}")

    async def list_sessions(self, user_id):
        now = datetime(2026, 7, 22, 17, tzinfo=UTC)
        return (SessionView(uuid.uuid4(), now, now, now + timedelta(days=1)),)

    async def revoke_session(self, **values):
        self.revoked = values


def _client():
    service = FakeSessionService()
    limiter = AllowingLimiter()
    runtime = SessionRuntime(
        service=service,
        rate_limiter=limiter,
        proxy_policy=TrustedProxyPolicy(),
        minimum_response_seconds=0,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session_runtime] = lambda: runtime
    app.dependency_overrides[get_identity_user] = lambda: {
        "user_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "session_type": "identity_user",
    }
    return TestClient(app, base_url="https://testserver"), service, limiter


def test_login_sets_secure_refresh_cookie_without_returning_refresh_token():
    client, service, limiter = _client()

    response = client.post(
        "/auth/login",
        json={"email": " Person@Example.com ", "password": "correct"},
    )

    assert response.status_code == 200
    assert response.json() == {"access_token": "access-one", "token_type": "bearer", "expires_in": 900}
    assert "refresh-one" not in response.text
    cookies = response.headers.get_list("set-cookie")
    assert any("pmk_refresh_token=refresh-one" in value and "HttpOnly" in value for value in cookies)
    assert all("Secure" in value and "SameSite=strict" in value for value in cookies)
    assert response.headers["cache-control"] == "no-store"
    assert service.login_calls == [{"email": "Person@Example.com", "password": "correct"}]
    assert limiter.calls[0]["subjects"]["email"] == "person@example.com"


def test_login_rejects_client_selected_role_without_reflecting_password():
    client, service, _ = _client()

    response = client.post(
        "/auth/login",
        json={
            "email": "person@example.com",
            "password": "password-must-not-be-reflected",
            "role": "admin",
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid session request."}
    assert "password-must-not-be-reflected" not in response.text
    assert service.login_calls == []


def test_refresh_requires_double_submit_csrf_before_service_call():
    client, service, _ = _client()
    client.cookies.set("pmk_refresh_token", "refresh-one", path="/auth/session")
    client.cookies.set("pmk_csrf_token", "csrf-one", path="/auth/session")

    denied = client.post("/auth/session/refresh")
    accepted = client.post(
        "/auth/session/refresh",
        headers={"X-CSRF-Token": "csrf-one"},
    )

    assert denied.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json()["access_token"] == "access-two"
    assert "refresh-two" not in accepted.text
    assert service.refresh_calls == ["refresh-one"]


def test_logout_revokes_server_session_and_clears_cookies():
    client, service, _ = _client()
    client.cookies.set("pmk_refresh_token", "refresh-one", path="/auth/session")
    client.cookies.set("pmk_csrf_token", "csrf-one", path="/auth/session")

    response = client.post(
        "/auth/session/logout",
        headers={"X-CSRF-Token": "csrf-one"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    assert service.logout_calls == ["refresh-one"]
    cookies = response.headers.get_list("set-cookie")
    assert sum("Max-Age=0" in value for value in cookies) == 2


def test_identity_user_can_list_and_revoke_owned_sessions():
    client, service, _ = _client()
    target_session_id = uuid.uuid4()

    listed = client.get("/auth/sessions")
    revoked = client.delete(f"/auth/sessions/{target_session_id}")

    assert listed.status_code == 200
    assert len(listed.json()["sessions"]) == 1
    assert revoked.status_code == 200
    assert service.revoked["session_id"] == target_session_id
