import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from processual_api.routers import settings as settings_router

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "processual_api" / "static"


def _admin_user() -> dict:
    return {
        "sub": "owner-admin",
        "user_id": "owner-admin",
        "client_id": "owner-admin",
        "role": "owner_admin",
        "session_type": "ui_admin",
        "scopes": ["admin:*", "admin:clients:read"],
    }


def _client_user() -> dict:
    return {
        "sub": "client-a",
        "user_id": "client-a",
        "client_id": "client-a",
        "role": "client",
        "session_type": "ui_client",
        "scopes": ["read:settings"],
    }


def test_admin_client_requests_route_is_registered() -> None:
    routes = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", []))))
        for route in settings_router.router.routes
    }

    assert any(
        path == "/settings/admin/client-requests" and "GET" in methods
        for path, methods in routes
    )


def test_admin_client_requests_endpoint_rejects_non_admin() -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(settings_router.list_admin_client_requests(_client_user()))

    assert exc.value.status_code == 403


def test_admin_client_requests_endpoint_returns_safe_empty_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    result = asyncio.run(settings_router.list_admin_client_requests(_admin_user()))

    assert result["status"] == "ready"
    assert result["request_count"] == 0
    assert result["latest_count"] == 0
    assert result["status_counts"] == {}
    assert result["latest_requests"] == []
    assert "Admin client requests inbox is ready." in result["message"]


def test_admin_client_requests_endpoint_returns_all_client_summaries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    settings_router._save_raw(
        "client-a",
        {
            "client_requests": [
                {
                    "id": "creq_alpha123456",
                    "status": "pending",
                    "source": "client_settings",
                    "created_at": "2026-07-04T10:00:00+00:00",
                    "updated_at": "2026-07-04T10:00:00+00:00",
                    "user_id": "client-a",
                    "client_id": "client-a",
                    "role": "client",
                    "request_type": "billing_usage_review",
                    "request_label": "Billing and usage review",
                    "requested_plan": "enterprise",
                    "message": "Please review usage and billing state safely.",
                }
            ]
        },
    )
    settings_router._save_raw(
        "client-b",
        {
            "client_requests": [
                {
                    "id": "creq_beta123456",
                    "status": "reviewed",
                    "source": "client_settings",
                    "created_at": "2026-07-04T11:00:00+00:00",
                    "updated_at": "2026-07-04T11:00:00+00:00",
                    "user_id": "client-b",
                    "client_id": "client-b",
                    "role": "client",
                    "request_type": "integration_key_provisioning",
                    "request_label": "Request integration key provisioning",
                    "requested_plan": "enterprise_integration",
                    "message": "Please provision an integration key safely.",
                }
            ]
        },
    )

    result = asyncio.run(settings_router.list_admin_client_requests(_admin_user()))

    assert result["status"] == "ready"
    assert result["request_count"] == 2
    assert result["latest_count"] == 2
    assert result["status_counts"] == {"reviewed": 1, "pending": 1}

    latest = result["latest_requests"]
    assert latest[0]["client_id"] == "client-b"
    assert latest[0]["request_type"] == "integration_key_provisioning"
    assert latest[1]["client_id"] == "client-a"
    assert latest[1]["request_type"] == "billing_usage_review"

    serialized = json.dumps(result, sort_keys=True)
    forbidden = [
        "api_key",
        "encrypted_key",
        "provider_secret",
        "raw key",
        "/settings/llm-provider",
    ]
    for marker in forbidden:
        assert marker not in serialized


def test_admin_client_requests_ui_hooks_are_registered() -> None:
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    required = [
        "Clients",
        "/console/js/admin_client_requests.js",
        "admin-client-requests-host",
        "admindirectplan07",
    ]
    for token in required:
        assert token in html


def test_admin_client_requests_script_uses_admin_endpoint_only() -> None:
    script = (STATIC_DIR / "js" / "admin_client_requests.js").read_text(
        encoding="utf-8"
    )

    required = [
        "PMK_ADMIN_CLIENT_REQUESTS",
        "HOST_ID",
        "/settings/admin/client-requests",
        "admin-client-requests-refresh-btn",
        "admin-client-requests-status",
        "admin-client-requests-counts",
        "admin-client-requests-list",
        "Client Requests Inbox",
        "latest_requests",
        "status_counts",
        "admin-client-request-actions",
        "admin-client-request-meta",
        "admin-client-request-row",
        "admin-client-request-grid",
        "admin-client-requests-style",
        "MutationObserver",
        "hashchange",
        "data-admin-page",
        "request_id",
        "short_id",
        "client_id",
        "request_type",
        "requested_plan",
        "status",
        "created_at",
        "source",
    ]
    for token in required:
        assert token in script

    forbidden = [
        "/settings/client-requests",
        "provider_secret",
        "encrypted_key",
        "raw key",
    ]
    for token in forbidden:
        assert token not in script
