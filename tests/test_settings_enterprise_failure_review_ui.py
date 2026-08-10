from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js" / "settings_enterprise_failure_review.js"
CSS = ROOT / "processual_api" / "static" / "css" / "settings_enterprise_failure_review.css"
ENDPOINT_JS = ROOT / "processual_api" / "static" / "js" / "settings_enterprise_endpoints.js"
APP = ROOT / "processual_api" / "static" / "js" / "app.js"


def test_failure_review_assets_are_bootstrapped_and_refresh_with_settings() -> None:
    js = JS.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    assert "PMK_SETTINGS_ENTERPRISE_FAILURE_REVIEW" in js
    assert "PMK_SETTINGS_ENTERPRISE_FAILURE_REVIEW" in app
    assert "settings_enterprise_failure_review.js" in app
    assert "settings_enterprise_failure_review.css" in app


def test_live_proof_ui_uses_reviewed_execution_path() -> None:
    endpoint_js = ENDPOINT_JS.read_text(encoding="utf-8")
    assert "/reviewed-sandbox-execute" in endpoint_js
    assert "refreshFailureReview" in endpoint_js
    assert "failure_review: result.failure_review" in endpoint_js


def test_failure_review_ui_exposes_actionable_lifecycle_not_raw_errors() -> None:
    js = JS.read_text(encoding="utf-8")
    lowered = js.lower()
    assert "/settings/enterprise-integration/sandbox-failures" in js
    assert "Failure review & recovery" in js
    assert "Sandbox reliability" in js
    assert "Recommended correction" in js
    assert "successful retest" in lowered
    assert "Raw errors hidden" in js
    assert "authorization" in lowered  # safe lifecycle stage name
    assert "raw exception" not in lowered
    assert "bearer " not in lowered
    assert "authorization:" not in lowered
    assert "authorization':" not in lowered
    assert "x-api-key" not in lowered
    assert "api_key_value" not in lowered


def test_failure_review_ui_has_progressive_disclosure_and_accessibility() -> None:
    js = JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert "document.createElement('details')" in js
    assert "document.createElement('summary')" in js
    assert "aria-live" in js
    assert "aria-labelledby" in js
    assert "role', 'note'" in js
    assert ":focus-visible" in css
    assert "border-inline-start" in css
    assert "@media(max-width:560px)" in css
    assert "prefers-reduced-motion" in css
