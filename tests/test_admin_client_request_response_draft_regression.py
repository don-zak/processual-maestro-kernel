import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "processual_api" / "routers" / "settings.py"
ADMIN_JS = ROOT / "processual_api" / "static" / "js" / "admin_client_requests.js"
ADMIN_HTML = ROOT / "processual_api" / "static" / "admin.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_admin_response_draft_backend_route_and_helpers_are_registered():
    source = _read(SETTINGS)

    assert '@router.post("/admin/client-requests/{request_id}/response-draft", response_model=dict)' in source
    assert "save_admin_client_request_response_draft" in source
    assert "_ADMIN_RESPONSE_DRAFT_FORBIDDEN_MARKERS" in source
    assert "_admin_response_draft_now_iso" in source
    assert "_admin_response_draft_actor" in source
    assert "_admin_safe_response_draft_text" in source
    assert "_admin_generate_supervisor_response_draft" in source
    assert "supervisor_response_drafts" in source
    assert "response_draft_saved" in source
    assert "admin_clients_panel" in source


def test_admin_response_draft_ui_surface_and_actions_are_wired():
    source = _read(ADMIN_JS)

    expected_markers = (
        "renderAdminClientRequestResponseDraftPanel",
        "generateAdminClientRequestResponseDraft",
        "saveAdminClientRequestResponseDraft",
        "copyAdminClientRequestResponseDraft",
        "admin-client-request-response-draft",
        "admin-client-request-response-draft-body",
        "admin-client-request-response-draft-status",
        "admin-client-request-response-draft-generate",
        "admin-client-request-response-draft-save",
        "Generate Draft",
        "Save Draft",
        "Copy Draft",
        "/response-draft",
    )

    for marker in expected_markers:
        assert marker in source


def test_admin_response_draft_global_exports_are_available():
    source = _read(ADMIN_JS)

    assert "window.PMK_ADMIN_CLIENT_REQUESTS" in source
    assert "generateAdminClientRequestResponseDraft" in source
    assert "saveAdminClientRequestResponseDraft" in source


def test_admin_response_draft_static_assets_do_not_expose_forbidden_markers():
    source = _read(ADMIN_JS)

    forbidden_markers = (
        "provider_secret",
        "encrypted_key",
        "raw key",
        "/settings/llm-provider",
        "/settings/api-keys",
    )

    for marker in forbidden_markers:
        assert marker not in source


def test_admin_response_draft_cache_version_is_bumped():
    html = _read(ADMIN_HTML)

    assert "admin_client_requests.js?v=adminrequests02b" in html
    assert "adminrequests01e" not in html

def _sample_client_request() -> dict:
    return {
        "id": "creq_behavior_12345678",
        "status": "pending",
        "source": "client_settings",
        "created_at": "2026-07-04T10:00:00+00:00",
        "updated_at": "2026-07-04T10:00:00+00:00",
        "user_id": "client_behavior",
        "client_id": "client_behavior",
        "role": "client",
        "request_type": "provider_setup_help",
        "requested_plan": "",
        "message": "Please help me verify my provider setup safely.",
        "status_history": [
            {
                "status": "pending",
                "at": "2026-07-04T10:00:00+00:00",
                "source": "client_settings",
            }
        ],
    }


def _write_request_store(tmp_path: Path) -> Path:
    path = tmp_path / "client_behavior_settings.json"
    path.write_text(
        json.dumps({"client_requests": [_sample_client_request()]}),
        encoding="utf-8",
    )
    return path


def _install_request_store(monkeypatch, tmp_path: Path) -> Path:
    from processual_api.routers import settings as settings_routes

    path = _write_request_store(tmp_path)
    monkeypatch.setattr(
        settings_routes,
        "_admin_client_request_raw_files",
        lambda: [path],
    )
    monkeypatch.setattr(
        settings_routes,
        "_admin_client_request_user_id_from_path",
        lambda _path: "client_behavior",
    )
    return path


def test_admin_response_draft_rejects_non_admin(tmp_path, monkeypatch):
    from processual_api.routers import settings as settings_routes

    _install_request_store(monkeypatch, tmp_path)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_routes.save_admin_client_request_response_draft(
                "creq_behavior_12345678",
                {"mode": "generate"},
                {"role": "client", "session_type": "client"},
            )
        )

    assert exc.value.status_code == 403


def test_admin_response_draft_generate_accepts_ui_admin_and_persists(
    tmp_path,
    monkeypatch,
):
    from processual_api.routers import settings as settings_routes

    store_path = _install_request_store(monkeypatch, tmp_path)

    result = asyncio.run(
        settings_routes.save_admin_client_request_response_draft(
            "creq_behavior_12345678",
            {"mode": "generate"},
            {
                "role": "admin",
                "session_type": "ui_admin",
                "user_id": "ui-admin-behavior",
            },
        )
    )

    assert result["status"] == "draft_saved"
    assert result["draft"]["state"] == "draft"
    assert result["draft"]["source"] == "admin_clients_panel"
    assert "provider setup request" in result["draft"]["body"]
    assert result["request"]["supervisor_response_drafts"]
    assert result["request"]["supervisor_response_drafts"][-1]["body"]

    raw = json.loads(store_path.read_text(encoding="utf-8"))
    entry = raw["client_requests"][0]
    assert entry["supervisor_response_drafts"]
    assert entry["supervisor_response_drafts"][-1]["mode"] == "generate"
    assert entry["status_history"][-1]["event"] == "response_draft_saved"
    assert entry["status_history"][-1]["source"] == "admin_clients_panel"


def test_admin_response_draft_manual_save_redacts_forbidden_markers(
    tmp_path,
    monkeypatch,
):
    from processual_api.routers import settings as settings_routes

    _install_request_store(monkeypatch, tmp_path)

    result = asyncio.run(
        settings_routes.save_admin_client_request_response_draft(
            "creq_behavior_12345678",
            {
                "mode": "manual",
                "draft": (
                    "Please do not share api_key, encrypted_key, provider_secret, "
                    "raw key, /settings/llm-provider, or /settings/api-keys."
                ),
                "template_id": "manual-test",
                "note": "manual save regression",
            },
            {
                "role": "admin",
                "session_type": "ui_admin",
                "user_id": "admin-behavior",
            },
        )
    )

    body = result["draft"]["body"].lower()
    forbidden = (
        "api_key",
        "encrypted_key",
        "provider_secret",
        "raw key",
        "/settings/llm-provider",
        "/settings/api-keys",
    )

    assert result["status"] == "draft_saved"
    assert "[redacted]" in body
    for marker in forbidden:
        assert marker not in body
    assert result["request"]["supervisor_response_drafts"][-1]["body"]
