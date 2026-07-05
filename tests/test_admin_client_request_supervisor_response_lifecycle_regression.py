from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_JS = ROOT / "processual_api" / "static" / "js" / "admin_client_requests.js"
ADMIN_HTML = ROOT / "processual_api" / "static" / "admin.html"
SETTINGS_PY = ROOT / "processual_api" / "routers" / "settings.py"
CLIENT_SETTINGS_JS = ROOT / "processual_api" / "static" / "js" / "pages" / "settings.js"


def test_admin_supervisor_response_lifecycle_prevents_duplicate_draft_send_static() -> None:
    admin_js = ADMIN_JS.read_text(encoding="utf-8")

    assert "draft_id" in admin_js
    assert "supervisor_response_sent" in admin_js
    assert "already sent" in admin_js.lower()
    assert "disable" in admin_js.lower() or ".disabled" in admin_js
    assert "Generate new response" in admin_js


def test_admin_supervisor_response_lifecycle_surfaces_sent_response_static() -> None:
    admin_js = ADMIN_JS.read_text(encoding="utf-8")
    admin_html = ADMIN_HTML.read_text(encoding="utf-8")

    combined = admin_html + "\n" + admin_js

    assert "Last sent response" in combined
    assert "Sent responses" in combined
    assert "supervisor_responses" in combined


def test_backend_supervisor_response_lifecycle_has_duplicate_guard_static() -> None:
    settings_py = SETTINGS_PY.read_text(encoding="utf-8")

    assert "_admin_find_supervisor_response_for_draft" in settings_py
    assert "already_sent" in settings_py
    assert "draft_id" in settings_py
    assert "supervisor_response_sent" in settings_py


def test_client_timeline_keeps_supervisor_response_deduplication_boundary_static() -> None:
    settings_js = CLIENT_SETTINGS_JS.read_text(encoding="utf-8")

    assert "supervisor_response_sent" in settings_js
    assert "draft_id" in settings_js
    assert "Set(" in settings_js or "seen" in settings_js.lower()
    assert "admin_" not in settings_js
