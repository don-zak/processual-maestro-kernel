from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.auth.security import get_current_user
from processual_api.routers import discord as discord_routes


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "root_path": "",
        }
    )


def _identity() -> dict:
    return {
        "sub": "user-1",
        "user_id": "user-1",
        "session_type": "identity_user",
        "session_id": "session-1",
    }


def test_discord_test_send_routes_require_authenticated_identity_dependency() -> None:
    test_send_routes = {
        route.path: route
        for route in discord_routes.router.routes
        if route.path in {"/discord/webhook/test", "/discord/webhook/test-admin"}
    }
    assert set(test_send_routes) == {
        "/discord/webhook/test",
        "/discord/webhook/test-admin",
    }
    for route in test_send_routes.values():
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        assert get_current_user in dependency_calls


@pytest.mark.parametrize(
    ("handler", "path"),
    [
        (discord_routes.test_discord_webhook, "/discord/webhook/test"),
        (discord_routes.test_discord_admin_webhook, "/discord/webhook/test-admin"),
    ],
)
def test_denied_platform_admin_authority_cannot_trigger_discord_side_effect(
    monkeypatch,
    handler,
    path: str,
) -> None:
    authority_calls: list[str] = []
    service_constructed = False

    async def deny(current_user: dict, request: Request | None = None) -> dict:
        authority_calls.append(request.method if request is not None else "")
        raise HTTPException(status_code=403, detail="platform admin required")

    class ForbiddenService:
        def __init__(self) -> None:
            nonlocal service_constructed
            service_constructed = True
            raise AssertionError("DiscordService must not be constructed before authority succeeds")

    monkeypatch.setattr(discord_routes, "require_active_platform_admin", deny)
    monkeypatch.setattr(discord_routes, "DiscordService", ForbiddenService)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            handler(
                discord_routes.DiscordWebhookTestRequest(message="must not send"),
                _request(path),
                _identity(),
            )
        )

    assert exc.value.status_code == 403
    assert authority_calls == ["POST"]
    assert service_constructed is False


def test_authorized_discord_test_send_runs_only_after_authority(monkeypatch) -> None:
    order: list[str] = []

    async def allow(current_user: dict, request: Request | None = None) -> dict:
        order.append("authority")
        assert request is not None
        assert request.method == "POST"
        return current_user

    class FakeService:
        has_client_webhook = True

        def __init__(self) -> None:
            order.append("service")

        async def send_client(self, message: str) -> bool:
            order.append("send")
            assert message == "authorized test"
            return True

    monkeypatch.setattr(discord_routes, "require_active_platform_admin", allow)
    monkeypatch.setattr(discord_routes, "DiscordService", FakeService)

    result = asyncio.run(
        discord_routes.test_discord_webhook(
            discord_routes.DiscordWebhookTestRequest(message="authorized test"),
            _request("/discord/webhook/test"),
            _identity(),
        )
    )

    assert result.success is True
    assert order == ["authority", "service", "send"]
