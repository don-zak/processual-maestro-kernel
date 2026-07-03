from __future__ import annotations

import asyncio

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError

from processual_api.routers import settings as settings_router


def test_client_requests_routes_are_registered() -> None:
    routes = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
    }

    assert any(path == "/settings/client-requests" for path, _ in routes)
    assert any(
        path == "/settings/client-request" and "POST" in methods
        for path, methods in routes
    )


def test_client_requests_list_returns_safe_empty_state(monkeypatch) -> None:
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: {})

    result = asyncio.run(
        settings_router.list_client_requests({
            "sub": "client-a",
            "user_id": "client-a",
            "client_id": "client-a",
            "role": "client",
        })
    )

    assert result["status"] == "ready"
    assert result["request_count"] == 0
    assert result["latest_requests"] == []
    assert {
        "id": "billing_usage_review",
        "label": "Billing and usage review",
    } in result["request_types"]


def test_submit_client_request_stores_pending_request_without_echoing_message(
    monkeypatch,
) -> None:
    saved: dict[str, object] = {}

    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: {})
    monkeypatch.setattr(
        settings_router,
        "_save_raw",
        lambda user_id, data: saved.update({"user_id": user_id, "data": data}),
    )

    result = asyncio.run(
        settings_router.submit_client_request(
            settings_router.ClientRequestPayload(
                request_type="billing_usage_review",
                requested_plan="enterprise_integration",
                message="Please review usage and billing before renewal.",
            ),
            {
                "sub": "client-a",
                "user_id": "client-a",
                "client_id": "tenant-a",
                "role": "client",
            },
        )
    )

    assert result["status"] == "submitted"
    assert result["request"]["status"] == "pending"
    assert result["request"]["request_type"] == "billing_usage_review"
    assert result["request"]["requested_plan"] == "enterprise_integration"
    assert "message" not in result["request"]

    assert saved["user_id"] == "client-a"
    stored = saved["data"]["client_requests"][0]
    assert stored["client_id"] == "tenant-a"
    assert stored["request_type"] == "billing_usage_review"
    assert stored["status"] == "pending"


def test_submit_client_request_normalizes_unknown_request_type(monkeypatch) -> None:
    saved: dict[str, object] = {}

    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: {})
    monkeypatch.setattr(
        settings_router,
        "_save_raw",
        lambda user_id, data: saved.update({"user_id": user_id, "data": data}),
    )

    result = asyncio.run(
        settings_router.submit_client_request(
            settings_router.ClientRequestPayload(
                request_type="unknown",
                requested_plan=None,
                message="Please contact me about onboarding next steps.",
            ),
            {
                "sub": "client-a",
                "user_id": "client-a",
                "client_id": "client-a",
                "role": "client",
            },
        )
    )

    assert result["request"]["request_type"] == "general_support"
    stored = saved["data"]["client_requests"][0]
    assert stored["request_type"] == "general_support"


def test_client_request_payload_requires_meaningful_message() -> None:
    with pytest.raises(ValidationError):
        settings_router.ClientRequestPayload(
            request_type="general_support",
            message="short",
        )
