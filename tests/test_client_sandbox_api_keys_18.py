from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from processual_api.routers import client_api_keys_18 as routes
from processual_api.routers import settings as settings_router

CLIENT = {
    "sub": "client-a",
    "user_id": "client-a",
    "client_id": "tenant-a",
    "role": "client",
}


def _patch_enterprise(monkeypatch, raw: dict, saved: dict) -> None:
    monkeypatch.setenv("PMK_DURABLE_SANDBOX_API_KEYS", "false")
    monkeypatch.setattr(settings_router, "_load_raw", lambda _user_id: raw)
    monkeypatch.setattr(
        settings_router,
        "_save_raw",
        lambda user_id, data: saved.update({"user_id": user_id, "data": data}),
    )
    monkeypatch.setattr(
        settings_router,
        "_resolve_client_api_key_integration_plan_id",
        lambda *_args, **_kwargs: "enterprise_integration",
    )
    monkeypatch.setattr(settings_router, "_allows_client_api_key_integration", lambda _plan: True)
    monkeypatch.setattr(routes, "generate_api_key", lambda: "pmk_test_visible_once_secret")
    monkeypatch.setattr(routes, "_hash", lambda _raw: "hashed-only")


def _patch_durable_enterprise(monkeypatch) -> dict:
    monkeypatch.setenv("PMK_DURABLE_SANDBOX_API_KEYS", "true")
    monkeypatch.setattr(settings_router, "_load_raw", lambda _user_id: {})
    monkeypatch.setattr(
        settings_router,
        "_resolve_client_api_key_integration_plan_id",
        lambda *_args, **_kwargs: "enterprise_integration",
    )
    monkeypatch.setattr(settings_router, "_allows_client_api_key_integration", lambda _plan: True)
    writes = {"legacy_save_calls": 0}

    def _legacy_save(*_args, **_kwargs):
        writes["legacy_save_calls"] += 1

    monkeypatch.setattr(settings_router, "_save_raw", _legacy_save)
    return writes


def test_client_sandbox_api_key_routes_are_registered() -> None:
    routes_index = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
    }
    assert ("/settings/client/api-keys", ("GET",)) in routes_index
    assert ("/settings/client/api-keys", ("POST",)) in routes_index
    assert any(path == "/settings/client/api-keys/{key_id}/rotate" for path, _ in routes_index)
    assert any(path == "/settings/client/api-keys/{key_id}" for path, _ in routes_index)


def test_client_can_create_read_only_sandbox_key_and_secret_is_visible_once(monkeypatch) -> None:
    raw: dict = {}
    saved: dict = {}
    _patch_enterprise(monkeypatch, raw, saved)

    result = asyncio.run(
        routes.create_client_sandbox_api_key(
            routes.ClientSandboxKeyCreate(
                profile_id="service_integration_read_only",
                label="CRM discovery",
                purpose="Read-only sandbox discovery",
                expires_in_days=30,
            ),
            CLIENT,
        )
    )

    assert result["status"] == "created"
    assert result["api_key"] == "pmk_test_visible_once_secret"
    assert result["visible_once"] is True
    assert result["key"]["environment"] == "sandbox"
    assert result["key"]["production_allowed"] is False
    assert result["key"]["runtime_connector_approved"] is False

    stored = saved["data"]["api_keys"][0]
    assert stored["hashed"] == "hashed-only"
    assert stored["self_service_sandbox"] is True
    assert stored["production_allowed"] is False
    assert "pmk_test_visible_once_secret" not in str(stored)

    listed = asyncio.run(routes.list_client_sandbox_api_keys(CLIENT))
    assert listed["key_count"] == 1
    assert "api_key" not in listed["keys"][0]
    assert "hashed" not in listed["keys"][0]
    assert "pmk_test_visible_once_secret" not in str(listed)


def test_durable_create_uses_postgres_service_and_never_legacy_save(monkeypatch) -> None:
    writes = _patch_durable_enterprise(monkeypatch)
    durable_key = {
        "key_id": "11111111-1111-1111-1111-111111111111",
        "prefix": "pmk_durable_...",
        "status": "enabled",
        "profile_id": "service_integration_read_only",
        "environment": "sandbox",
        "scopes": ["read:health"],
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }

    async def _issue(**kwargs):
        assert kwargs["client_ref"] == "tenant-a"
        assert kwargs["owner_user_ref"] == "client-a"
        assert kwargs["plan_code"] == "enterprise_integration"
        assert kwargs["profile_id"] == "service_integration_read_only"
        return durable_key, "pmk_durable_visible_once"

    monkeypatch.setattr(routes, "issue_durable_sandbox_api_key", _issue)

    result = asyncio.run(
        routes.create_client_sandbox_api_key(
            routes.ClientSandboxKeyCreate(
                profile_id="service_integration_read_only",
                label="Durable CRM discovery",
                purpose="PostgreSQL authority proof",
                expires_in_days=30,
            ),
            CLIENT,
        )
    )

    assert result["api_key"] == "pmk_durable_visible_once"
    assert result["visible_once"] is True
    assert result["key"] == durable_key
    assert writes["legacy_save_calls"] == 0
    assert "pmk_durable_visible_once" not in str(result["key"])


def test_durable_list_rotate_and_revoke_never_use_legacy_save(monkeypatch) -> None:
    writes = _patch_durable_enterprise(monkeypatch)
    durable_key = {
        "key_id": "11111111-1111-1111-1111-111111111111",
        "prefix": "pmk_durable_...",
        "status": "enabled",
        "profile_id": "service_integration_read_only",
        "environment": "sandbox",
        "scopes": ["read:health"],
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }
    calls: list[str] = []

    async def _list(**kwargs):
        calls.append("list")
        assert kwargs == {"client_ref": "tenant-a", "plan_code": "enterprise_integration"}
        return [durable_key]

    async def _rotate(**kwargs):
        calls.append("rotate")
        assert kwargs["key_id"] == durable_key["key_id"]
        return durable_key, "pmk_rotated_visible_once"

    async def _revoke(**kwargs):
        calls.append("revoke")
        assert kwargs["key_id"] == durable_key["key_id"]
        return durable_key

    monkeypatch.setattr(routes, "list_durable_sandbox_api_keys", _list)
    monkeypatch.setattr(routes, "rotate_durable_sandbox_api_key", _rotate)
    monkeypatch.setattr(routes, "revoke_durable_sandbox_api_key", _revoke)

    listed = asyncio.run(routes.list_client_sandbox_api_keys(CLIENT))
    rotated = asyncio.run(
        routes.rotate_client_sandbox_api_key(
            durable_key["key_id"],
            routes.ClientSandboxKeyRotate(expires_in_days=30),
            CLIENT,
        )
    )
    revoked = asyncio.run(
        routes.revoke_client_sandbox_api_key(durable_key["key_id"], CLIENT)
    )

    assert listed["keys"] == [durable_key]
    assert rotated["api_key"] == "pmk_rotated_visible_once"
    assert rotated["visible_once"] is True
    assert revoked["status"] == "revoked"
    assert calls == ["list", "rotate", "revoke"]
    assert writes["legacy_save_calls"] == 0


def test_client_self_service_rejects_write_profile(monkeypatch) -> None:
    raw: dict = {}
    saved: dict = {}
    _patch_enterprise(monkeypatch, raw, saved)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            routes.create_client_sandbox_api_key(
                routes.ClientSandboxKeyCreate(
                    profile_id="telecom_operations_sandbox",
                    label="Telecom write sandbox",
                    purpose="Write operation",
                ),
                CLIENT,
            )
        )

    assert exc.value.status_code == 403
    assert "supervisor approval" in str(exc.value.detail).lower()
    assert saved == {}


def test_client_self_service_rejects_ineligible_plan(monkeypatch) -> None:
    monkeypatch.setenv("PMK_DURABLE_SANDBOX_API_KEYS", "false")
    monkeypatch.setattr(settings_router, "_load_raw", lambda _user_id: {})
    monkeypatch.setattr(
        settings_router,
        "_resolve_client_api_key_integration_plan_id",
        lambda *_args, **_kwargs: "starter",
    )
    monkeypatch.setattr(settings_router, "_allows_client_api_key_integration", lambda _plan: False)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(routes.list_client_sandbox_api_keys(CLIENT))

    assert exc.value.status_code == 403
    assert "Enterprise Integration" in str(exc.value.detail)
