from __future__ import annotations

import pytest
from starlette.requests import Request

from processual_api.middleware.security_headers import SecurityHeadersMiddleware
from processual_api.services import evaluation_launch_gate as launch


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, *, ex: int, nx: bool):
        assert ex == launch.EVALUATION_LAUNCH_TICKET_TTL_SECONDS
        assert nx is True
        if key in self.values:
            return False
        self.values[key] = value
        return True

    async def getdel(self, key: str):
        return self.values.pop(key, None)


def _request(*, destination: str, query: str = "", cookie: str = "") -> Request:
    headers = [(b"sec-fetch-dest", destination.encode("ascii"))]
    if cookie:
        headers.append((b"cookie", cookie.encode("ascii")))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/console/evaluation.html",
            "raw_path": b"/console/evaluation.html",
            "query_string": query.encode("ascii"),
            "headers": headers,
            "client": ("203.0.113.10", 443),
            "server": ("example.test", 443),
        }
    )


@pytest.mark.asyncio
async def test_launch_ticket_is_one_time_and_session_is_long_enough(monkeypatch):
    fake_redis = _FakeRedis()

    async def fake_get_redis():
        return fake_redis

    async def fake_require_active_grant(owner_user_id: str, grant_id: str):
        assert owner_user_id == "admin-1"
        assert grant_id == "eval-1"
        return {"grant_id": grant_id, "status": "active", "production_allowed": False}

    monkeypatch.setattr(launch, "get_redis", fake_get_redis)
    monkeypatch.setattr(launch, "_require_active_grant", fake_require_active_grant)
    monkeypatch.setattr(launch.settings, "jwt_secret", "test-launch-secret-not-for-production")

    issued = await launch.issue_evaluation_launch_ticket(
        owner_user_id="admin-1",
        grant_id="eval-1",
        now=1_000_000,
    )
    assert issued["expires_in_seconds"] == 30 * 60
    assert issued["workspace_session_seconds"] == 2 * 60 * 60
    assert issued["one_time"] is True
    assert issued["execution_authority_replaced"] is False

    session_token, session = await launch.redeem_evaluation_launch_ticket(
        issued["launch_ticket"],
        now=1_000_100,
    )
    assert session.expires_at - session.issued_at == 2 * 60 * 60
    assert session.grant_id == "eval-1"

    validated = await launch.validate_evaluation_workspace_session(
        session_token,
        now=1_000_200,
    )
    assert validated.grant_id == "eval-1"

    with pytest.raises(
        launch.EvaluationLaunchGateError,
        match="evaluation_launch_ticket_consumed_or_expired",
    ):
        await launch.redeem_evaluation_launch_ticket(
            issued["launch_ticket"],
            now=1_000_300,
        )


@pytest.mark.asyncio
async def test_workspace_blocks_direct_top_level_navigation():
    middleware = SecurityHeadersMiddleware(lambda scope, receive, send: None)
    response = await middleware._evaluation_workspace_gate(_request(destination="document"))
    assert response is not None
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_workspace_iframe_still_requires_launch_authority():
    middleware = SecurityHeadersMiddleware(lambda scope, receive, send: None)
    response = await middleware._evaluation_workspace_gate(_request(destination="iframe"))
    assert response is not None
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_launch_redeem_redirect_sets_cross_site_httponly_cookie(monkeypatch):
    async def fake_redeem(_token: str):
        return "session-token", launch.EvaluationLaunchSession(
            owner_user_id="admin-1",
            grant_id="eval-1",
            issued_at=10,
            expires_at=20,
        )

    import processual_api.middleware.security_headers as middleware_module

    monkeypatch.setattr(middleware_module, "redeem_evaluation_launch_ticket", fake_redeem)
    middleware = SecurityHeadersMiddleware(lambda scope, receive, send: None)
    response = await middleware._evaluation_workspace_gate(
        _request(destination="iframe", query="launch=one-time-ticket")
    )
    assert response is not None
    assert response.status_code == 303
    assert response.headers["location"] == "/console/evaluation.html"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=none" in cookie
    assert f"max-age={2 * 60 * 60}" in cookie
