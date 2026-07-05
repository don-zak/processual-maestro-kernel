import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from processual_api.routers import settings as settings_routes

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "processual_api" / "routers" / "settings.py"
ADMIN_JS = ROOT / "processual_api" / "static" / "js" / "admin_client_requests.js"
CLIENT_SETTINGS_JS = ROOT / "processual_api" / "static" / "js" / "pages" / "settings.js"
INDEX_HTML = ROOT / "processual_api" / "static" / "index.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_admin_supervisor_response_backend_route_and_helpers_are_registered():
    source = _read(SETTINGS)

    assert '@router.post("/admin/client-requests/{request_id}/supervisor-response", response_model=dict)' in source
    assert "send_admin_client_request_supervisor_response" in source
    assert "_admin_supervisor_response_now_iso" in source
    assert "_admin_supervisor_response_actor" in source
    assert "_admin_safe_supervisor_response_text" in source
    assert "_append_admin_supervisor_response_history" in source
    assert "supervisor_response_sent" in source
    assert "admin_clients_panel" in source


def test_admin_supervisor_response_ui_send_action_is_wired():
    source = _read(ADMIN_JS)

    expected = (
        "sendAdminClientRequestSupervisorResponse",
        "admin-client-request-response-draft-send",
        "Send Response",
        "/supervisor-response",
        "supervisor_response_sent",
    )

    for marker in expected:
        assert marker in source


def test_client_timeline_can_surface_supervisor_response():
    source = _read(CLIENT_SETTINGS_JS)

    expected = (
        "supervisor_response",
        "supervisor_response_sent",
        "Supervisor response",
        "response.source",
    )

    for marker in expected:
        assert marker in source


def test_admin_supervisor_response_ui_does_not_expose_forbidden_markers():
    source = _read(ADMIN_JS)

    forbidden = (
        "provider_secret",
        "encrypted_key",
        "raw key",
        "/settings/llm-provider",
        "/settings/api-keys",
    )

    for marker in forbidden:
        assert marker not in source

def _supervisor_response_entry() -> dict:
    return {
        "id": "creq_supervisor_response",
        "status": "reviewed",
        "source": "client_settings",
        "created_at": "2026-07-04T20:00:00+00:00",
        "updated_at": "2026-07-04T20:00:00+00:00",
        "user_id": "client-alpha",
        "client_id": "client-alpha",
        "role": "client",
        "request_type": "enterprise_integration_upgrade",
        "request_label": "Enterprise integration upgrade",
        "requested_plan": "enterprise",
        "message": "Please review our enterprise integration request.",
        "supervisor_response_drafts": [
            {
                "draft_id": "rdraft_safe",
                "request_id": "creq_supervisor_response",
                "body": "Thanks. We reviewed your request and will follow up safely.",
                "created_at": "2026-07-04T20:05:00+00:00",
                "updated_at": "2026-07-04T20:05:00+00:00",
                "source": "admin_clients_panel",
                "state": "draft",
                "mode": "manual",
                "actor": "admin@example.test",
            }
        ],
    }


def _write_supervisor_response_file(tmp_path, entry=None):
    path = tmp_path / "settings_client-alpha.json"
    raw = {"client_requests": [entry or _supervisor_response_entry()]}
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _patch_supervisor_response_files(monkeypatch, path):
    monkeypatch.setattr(settings_routes, "_admin_client_request_raw_files", lambda: [path])
    monkeypatch.setattr(
        settings_routes,
        "_admin_client_request_user_id_from_path",
        lambda _path: "client-alpha",
    )


def test_admin_supervisor_response_rejects_non_admin(tmp_path, monkeypatch):
    path = _write_supervisor_response_file(tmp_path)
    _patch_supervisor_response_files(monkeypatch, path)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_routes.send_admin_client_request_supervisor_response(
                "creq_supervisor_response",
                {"draft_id": "rdraft_safe"},
                current_user={"role": "client", "user_id": "client-alpha"},
            )
        )

    assert exc.value.status_code == 403


def test_admin_supervisor_response_sends_latest_draft_to_client_timeline(tmp_path, monkeypatch):
    path = _write_supervisor_response_file(tmp_path)
    _patch_supervisor_response_files(monkeypatch, path)

    result = asyncio.run(
        settings_routes.send_admin_client_request_supervisor_response(
            "creq_supervisor_response",
            {"draft_id": "rdraft_safe"},
            current_user={
                "role": "admin",
                "session_type": "ui_admin",
                "email": "admin@example.test",
            },
        )
    )

    assert result["status"] == "sent"
    assert result["message"] == "Supervisor response sent to client timeline."
    assert result["supervisor_response"]["event"] == "supervisor_response_sent"
    assert result["supervisor_response"]["source"] == "admin_clients_panel"
    assert result["supervisor_response"]["body"].startswith("Thanks.")

    raw = json.loads(path.read_text(encoding="utf-8"))
    entry = raw["client_requests"][0]
    assert entry["supervisor_responses"][0]["event"] == "supervisor_response_sent"
    assert entry["supervisor_responses"][0]["body"].startswith("Thanks.")
    assert entry["supervisor_response_drafts"][0]["state"] == "sent"
    assert any(
        event.get("event") == "supervisor_response_sent"
        for event in entry.get("status_history", [])
    )


def test_admin_supervisor_response_manual_body_is_redacted_before_persisting(
    tmp_path,
    monkeypatch,
):
    path = _write_supervisor_response_file(tmp_path)
    _patch_supervisor_response_files(monkeypatch, path)

    result = asyncio.run(
        settings_routes.send_admin_client_request_supervisor_response(
            "creq_supervisor_response",
            {
                "body": (
                    "Do not expose api_key provider_secret encrypted_key raw key "
                    "/settings/llm-provider /settings/api-keys"
                )
            },
            current_user={"role": "admin", "email": "admin@example.test"},
        )
    )

    body = result["supervisor_response"]["body"].lower()
    for marker in (
        "api_key",
        "provider_secret",
        "encrypted_key",
        "raw key",
        "/settings/llm-provider",
        "/settings/api-keys",
    ):
        assert marker not in body
    assert "[redacted]" in result["supervisor_response"]["body"]


def test_client_request_summary_includes_supervisor_responses(monkeypatch):
    entry = _supervisor_response_entry()
    entry["supervisor_responses"] = [
        {
            "response_id": "sresp_1",
            "request_id": "creq_supervisor_response",
            "draft_id": "rdraft_safe",
            "body": "Supervisor response visible to the client.",
            "sent_at": "2026-07-04T20:10:00+00:00",
            "source": "admin_clients_panel",
            "state": "sent",
            "actor": "admin@example.test",
            "event": "supervisor_response_sent",
        }
    ]

    monkeypatch.setattr(settings_routes, "_load_raw", lambda _user_id: {"client_requests": [entry]})

    result = asyncio.run(
        settings_routes.list_client_requests(
            current_user={"user_id": "client-alpha", "sub": "client-alpha"}
        )
    )

    latest = result["latest_requests"][0]
    assert latest["supervisor_responses"][0]["event"] == "supervisor_response_sent"
    assert latest["supervisor_responses"][0]["source"] == "admin_clients_panel"
    assert latest["supervisor_responses"][0]["body"] == "Supervisor response visible to the client."

def test_client_settings_cache_is_bumped_for_supervisor_response_timeline():
    source = _read(INDEX_HTML)

    assert "pages/settings.js?v=settingsrequests02brefresh" in source

def test_client_settings_refresh_loads_client_request_timeline():
    source = _read(CLIENT_SETTINGS_JS)

    assert "async function refresh()" in source
    assert "await loadClientRequests();" in source
    assert "function loadClientRequests()" in source
    assert "applyClientRequests(info)" in source

