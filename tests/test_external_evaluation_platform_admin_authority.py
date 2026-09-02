from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request

from processual_api.admin_marketplace.errors import AdminMarketplaceAuthorityDeniedError
from processual_api.auth import platform_admin_authority


IDENTITY = {
    "user_id": "11111111-1111-1111-1111-111111111111",
    "session_id": "22222222-2222-2222-2222-222222222222",
    "session_type": "identity_user",
}


def _request(method: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/settings/admin/evaluation-grants",
            "raw_path": b"/settings/admin/evaluation-grants",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "root_path": "",
        }
    )


def _runtime(*, active: bool = True, recent_mfa: bool = True):
    class Resolver:
        async def resolve(self, *, user_id: str, session_id: str):
            assert user_id == IDENTITY["user_id"]
            assert session_id == IDENTITY["session_id"]
            return SimpleNamespace(
                active_platform_admin=active,
                recent_mfa_step_up=recent_mfa,
            )

    return SimpleNamespace(authority_resolver=Resolver())


@pytest.mark.asyncio
async def test_persisted_platform_admin_is_accepted_for_read(monkeypatch) -> None:
    async def build_runtime():
        return _runtime()

    monkeypatch.setattr(platform_admin_authority, "build_admin_marketplace_runtime", build_runtime)
    identity = dict(IDENTITY)
    assert (
        await platform_admin_authority.require_active_platform_admin(
            identity,
            _request("GET"),
        )
        is identity
    )


@pytest.mark.asyncio
async def test_sensitive_evaluation_admin_action_requires_recent_mfa(monkeypatch) -> None:
    async def build_runtime():
        return _runtime(recent_mfa=False)

    monkeypatch.setattr(platform_admin_authority, "build_admin_marketplace_runtime", build_runtime)
    with pytest.raises(HTTPException) as exc_info:
        await platform_admin_authority.require_active_platform_admin(
            dict(IDENTITY),
            _request("POST"),
        )
    assert exc_info.value.status_code == 428


@pytest.mark.asyncio
async def test_non_identity_api_key_cannot_administer_evaluation(monkeypatch) -> None:
    async def build_runtime():
        raise AssertionError("runtime must not be consulted for an API-key identity")

    monkeypatch.setattr(platform_admin_authority, "build_admin_marketplace_runtime", build_runtime)
    with pytest.raises(HTTPException) as exc_info:
        await platform_admin_authority.require_active_platform_admin(
            {
                "user_id": "api-key-owner",
                "session_type": "api_key",
                "role": "platform_admin",
            },
            _request("POST"),
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_denied_persisted_authority_is_rejected(monkeypatch) -> None:
    class Resolver:
        async def resolve(self, **kwargs):
            raise AdminMarketplaceAuthorityDeniedError("denied")

    async def build_runtime():
        return SimpleNamespace(authority_resolver=Resolver())

    monkeypatch.setattr(platform_admin_authority, "build_admin_marketplace_runtime", build_runtime)
    with pytest.raises(HTTPException) as exc_info:
        await platform_admin_authority.require_active_platform_admin(
            dict(IDENTITY),
            _request("GET"),
        )
    assert exc_info.value.status_code == 403
