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


def _seed_request() -> dict:
    return {
        "id": "creq_alpha123456",
        "status": "pending",
        "source": "client_settings",
        "created_at": "2026-07-04T10:00:00+00:00",
        "updated_at": "2026-07-04T10:05:00+00:00",
        "user_id": "client-a",
        "client_id": "client-a",
        "role": "client",
        "request_type": "provider_setup_help",
        "request_label": "Provider setup help",
        "requested_plan": "enterprise",
        "message": (
            "Please help. This text mentions api_key, encrypted_key, "
            "provider_secret, raw key, and /settings/llm-provider."
        ),
        "status_history": [
            {
                "status": "pending",
                "at": "2026-07-04T10:00:00+00:00",
                "source": "client_settings",
            }
        ],
    }


def test_admin_client_request_detail_route_is_registered() -> None:
    routes = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", []))))
        for route in settings_router.router.routes
    }

    assert any(
        path == "/settings/admin/client-requests/{request_id}" and "GET" in methods
        for path, methods in routes
    )


def test_admin_client_request_detail_rejects_non_admin() -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_router.get_admin_client_request_detail(
                "creq_alpha123456",
                _client_user(),
            )
        )

    assert exc.value.status_code == 403


def test_admin_client_request_detail_returns_safe_detail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    settings_router._save_raw("client-a", {"client_requests": [_seed_request()]})

    result = asyncio.run(
        settings_router.get_admin_client_request_detail(
            "creq_alpha123456",
            _admin_user(),
        )
    )

    assert result["status"] == "ready"
    detail = result["request"]

    assert detail["request_id"] == "creq_alpha123456"
    assert detail["short_id"] == "ha123456"
    assert detail["client_id"] == "client-a"
    assert detail["request_type"] == "provider_setup_help"
    assert detail["request_label"] == "Provider setup help"
    assert detail["requested_plan"] == "enterprise"
    assert detail["status"] == "pending"
    assert detail["created_at"] == "2026-07-04T10:00:00+00:00"
    assert detail["updated_at"] == "2026-07-04T10:05:00+00:00"
    assert detail["timeline"] == [
        {
            "status": "pending",
            "at": "2026-07-04T10:00:00+00:00",
            "source": "client_settings",
        }
    ]
    assert "Review" in detail["next_admin_action"]

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


def test_admin_client_request_detail_can_load_by_short_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    settings_router._save_raw("client-a", {"client_requests": [_seed_request()]})

    result = asyncio.run(
        settings_router.get_admin_client_request_detail("ha123456", _admin_user())
    )

    assert result["status"] == "ready"
    assert result["request"]["request_id"] == "creq_alpha123456"


def test_admin_client_request_detail_missing_returns_404(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_router.get_admin_client_request_detail("missing", _admin_user())
        )

    assert exc.value.status_code == 404


def test_admin_client_request_detail_ui_hooks_exist() -> None:
    script = (STATIC_DIR / "js" / "admin_client_requests.js").read_text(
        encoding="utf-8"
    )

    required = [
        "PMK_ADMIN_CLIENT_REQUESTS",
        "loadAdminClientRequestDetail",
        "renderAdminClientRequestDetail",
        "/settings/admin/client-requests/",
        "admin-client-request-detail",
        "admin-client-request-detail-status",
        "admin-client-request-detail-body",
        "timeline",
        "next_admin_action",
        "admin-client-request-select",
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


def test_admin_client_request_detail_cache_version_is_updated() -> None:
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    assert "/console/js/admin_client_requests.js" in html
    assert "adminrequests02b" in html
