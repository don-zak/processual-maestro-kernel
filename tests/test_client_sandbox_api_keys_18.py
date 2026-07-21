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
