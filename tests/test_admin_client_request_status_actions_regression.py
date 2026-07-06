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
        "scopes": ["admin:*", "admin:clients:read", "admin:clients:write"],
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
        "id": "creq_status123456",
        "status": "pending",
        "source": "client_settings",
        "created_at": "2026-07-04T10:00:00+00:00",
        "updated_at": "2026-07-04T10:00:00+00:00",
        "user_id": "client-a",
        "client_id": "client-a",
        "role": "client",
        "request_type": "enterprise_integration_upgrade",
        "request_label": "Upgrade to Enterprise Integration",
        "requested_plan": "enterprise",
        "message": "Client is asking for an upgrade.",
        "status_history": [
            {
                "status": "pending",
                "at": "2026-07-04T10:00:00+00:00",
                "source": "client_settings",
            }
        ],
    }


def test_admin_client_request_status_route_is_registered() -> None:
    routes = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", []))))
        for route in settings_router.router.routes
    }

    assert any(
        path == "/settings/admin/client-requests/{request_id}/status"
        and "POST" in methods
        for path, methods in routes
    )


def test_admin_client_request_status_rejects_non_admin() -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_router.update_admin_client_request_status(
                "creq_status123456",
                {"status": "reviewed"},
                _client_user(),
            )
        )

    assert exc.value.status_code == 403




def test_admin_client_request_status_allows_ui_admin_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    settings_router._save_raw("client-a", {"client_requests": [_seed_request()]})

    ui_admin = {
        "sub": "browser-admin",
        "user_id": "browser-admin",
        "client_id": "browser-admin",
        "role": "admin",
        "session_type": "ui_admin",
        "scopes": ["admin:clients:read"],
    }

    result = asyncio.run(
        settings_router.update_admin_client_request_status(
            "creq_status123456",
            {"status": "reviewed", "note": "Reviewed from browser."},
            ui_admin,
        )
    )

    assert result["status"] == "updated"
    assert result["request"]["status"] == "reviewed"
    assert result["request"]["timeline"][-1]["source"] == "admin_clients_panel"

def test_admin_client_request_status_rejects_invalid_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    settings_router._save_raw("client-a", {"client_requests": [_seed_request()]})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_router.update_admin_client_request_status(
                "creq_status123456",
                {"status": "dangerous"},
                _admin_user(),
            )
        )

    assert exc.value.status_code == 422


def test_admin_client_request_status_update_saves_history(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    settings_router._save_raw("client-a", {"client_requests": [_seed_request()]})

    result = asyncio.run(
        settings_router.update_admin_client_request_status(
            "creq_status123456",
            {
                "status": "reviewed",
                "note": "Reviewed. Mentions api_key and provider_secret.",
            },
            _admin_user(),
        )
    )

    assert result["status"] == "updated"
    detail = result["request"]
    assert detail["request_id"] == "creq_status123456"
    assert detail["status"] == "reviewed"
    assert detail["timeline"][-1]["status"] == "reviewed"
    assert detail["timeline"][-1]["source"] == "admin_clients_panel"
    assert "Review" not in detail["next_admin_action"]

    serialized = json.dumps(result, sort_keys=True)
    forbidden = ["api_key", "provider_secret", "encrypted_key", "raw key"]
    for marker in forbidden:
        assert marker not in serialized

    saved_files = list(tmp_path.rglob("*.json"))
    assert saved_files

    saved = json.loads(saved_files[0].read_text(encoding="utf-8"))
    history = saved["client_requests"][0]["status_history"]
    assert history[-1]["status"] == "reviewed"
    assert history[-1]["source"] == "admin_clients_panel"
    assert history[-1]["note"] == "[redacted]"


def test_admin_client_request_status_update_can_load_by_short_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    settings_router._save_raw("client-a", {"client_requests": [_seed_request()]})

    result = asyncio.run(
        settings_router.update_admin_client_request_status(
            "us123456",
            {"status": "completed", "note": "Done."},
            _admin_user(),
        )
    )

    assert result["status"] == "updated"
    assert result["request"]["request_id"] == "creq_status123456"
    assert result["request"]["status"] == "completed"


def test_admin_client_request_status_missing_returns_404(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_router.update_admin_client_request_status(
                "missing",
                {"status": "reviewed"},
                _admin_user(),
            )
        )

    assert exc.value.status_code == 404


def test_admin_client_request_status_action_ui_hooks_exist() -> None:
    script = (STATIC_DIR / "js" / "admin_client_requests.js").read_text(
        encoding="utf-8"
    )

    required = [
        "updateAdminClientRequestStatus",
        "renderAdminClientRequestStatusActions",
        "admin-client-request-status-action",
        "admin-client-request-status-actions",
        "/settings/admin/client-requests/",
        "/status",
        "Mark Reviewed",
        "Approve",
        "Reject",
        "Complete",
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


def test_admin_client_request_status_action_cache_version_is_updated() -> None:
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    assert "/console/js/admin_client_requests.js" in html
    assert "adminapplyplan02" in html
