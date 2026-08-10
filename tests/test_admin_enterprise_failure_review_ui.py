from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js" / "admin_enterprise_failure_review.js"
CSS = ROOT / "processual_api" / "static" / "css" / "admin_enterprise_failure_review.css"
ACTIONS = ROOT / "processual_api" / "static" / "js" / "admin_actions.js"
AUTH = ROOT / "processual_api" / "static" / "js" / "admin_auth_bridge.js"


def test_admin_failure_review_assets_are_bootstrapped_from_admin_shell() -> None:
    js = JS.read_text(encoding="utf-8")
    actions = ACTIONS.read_text(encoding="utf-8")
    assert "PMK_ADMIN_ENTERPRISE_FAILURE_REVIEW" in js
    assert "admin_enterprise_failure_review.js" in actions
    assert "admin_enterprise_failure_review.css" in actions
    assert "loadEnterpriseFailureReview" in actions


def test_admin_queue_uses_existing_supervisor_session_bridge() -> None:
    js = JS.read_text(encoding="utf-8")
    auth = AUTH.read_text(encoding="utf-8")
    assert "PMK_ADMIN_AUTH?.headers" in js
    assert "supervisorSessionKeyFound" in js
    assert "X-Supervisor-Session-Key" in auth
    assert "/settings/admin/integration-tasks/" in js
    assert "/sandbox-failures/" in js
    assert "/review" in js


def test_admin_queue_never_claims_manual_review_resolves_failure() -> None:
    js = JS.read_text(encoding="utf-8")
    lowered = js.lower()
    assert "Start review" in js
    assert "successful customer sandbox retest" in lowered
    assert "does not alter customer bindings" in lowered
    assert "production authority" in lowered
    assert "ignore failure" not in lowered
    assert "mark resolved" not in lowered


def test_admin_failure_review_is_actionable_accessible_and_responsive() -> None:
    js = JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert "Failure review queue" in js
    assert "Recommended correction" in js
    assert "document.createElement('details')" in js
    assert "aria-live" in js
    assert "aria-labelledby" in js
    assert "role', 'note'" in js
    assert ":focus-visible" in css
    assert "border-inline-start" in css
    assert "@media(max-width:560px)" in css
    assert "prefers-reduced-motion" in css


def test_admin_failure_review_does_not_render_raw_failure_or_credentials() -> None:
    js = JS.read_text(encoding="utf-8").lower()
    assert "raw error" in js  # explanatory safety copy only
    assert "raw_error" not in js
    assert "credential value" not in js
    assert "bearer " not in js
    assert "authorization:" not in js
