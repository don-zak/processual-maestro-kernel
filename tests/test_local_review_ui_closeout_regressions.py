from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONSOLE_I18N = ROOT / "processual_api" / "static" / "js" / "i18n.js"
LOGIN_RUNTIME = ROOT / "processual_api" / "static" / "js" / "login_token_capture.js"
FULL_REVIEW = ROOT / "scripts" / "run_full_web_review.ps1"


def test_console_language_control_is_removed_not_only_hidden() -> None:
    source = CONSOLE_I18N.read_text(encoding="utf-8")

    assert "I18N.setLang('en')" in source
    assert "document.documentElement.dir = 'ltr'" in source
    assert "toggle.remove()" in source
    assert "toggle.hidden = true" not in source


def test_login_expanded_panels_are_viewport_safe_and_scrollable() -> None:
    source = LOGIN_RUNTIME.read_text(encoding="utf-8")

    assert "function installViewportSafeLoginLayout()" in source
    assert "body{overflow-x:hidden!important;overflow-y:auto!important;}" in source
    assert "@media (max-height:900px)" in source
    assert "body{align-items:flex-start!important;}" in source
    assert ".login-wrap{margin:0 auto;padding-top:24px;padding-bottom:32px;}" in source
    assert "installViewportSafeLoginLayout();" in source


def test_full_review_reset_releases_only_its_stale_uvicorn_servers() -> None:
    source = FULL_REVIEW.read_text(encoding="utf-8")

    assert "function Stop-StaleLocalReviewServers" in source
    assert "processual_api\\.main:app" in source
    assert "--no-access-log" in source
    assert "Stop-Process -Id $pidValue -Force" in source
    assert "if ($ResetDatabase)" in source
    assert "Released $($releasedPids.Count) stale local-review server process(es)." in source


def test_review_checklist_covers_console_language_and_lost_access_overflow() -> None:
    source = FULL_REVIEW.read_text(encoding="utf-8")

    assert "Confirm the Console exposes no AR language control" in source
    assert "Expand Lost Access on short/narrow login viewports" in source
