from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_viewport_hardening_uses_full_screen_and_scroll_container():
    css = read("processual_api/static/css/runtime_viewport_hardening.css")
    assert "height: 100vh" in css
    assert "#main" in css
    assert "max-height: 100vh" in css
    assert "#content" in css
    assert "overflow-y: auto !important" in css
    assert "#content > .page.active" in css
    assert "min-height: 100%" in css


def test_admin_home_does_not_subtract_artificial_viewport_height():
    source = read("processual_api/static/js/admin_home_layout.js")
    assert "calc(100vh - 76px)" not in source
    assert "#main{height:100vh!important" in source
    assert "max-height:100vh!important" in source
    assert "padding-bottom:0!important" in source


def test_console_html_and_assets_are_no_store_and_badge_is_rewritten_server_side():
    source = read("processual_api/middleware/security_headers.py")
    assert '(b"Demo Mode", b"Qualification Ready")' in source
    assert 'path.startswith("/console/")' in source
    assert "no-store, no-cache, must-revalidate, max-age=0" in source
    assert "_RUNTIME_VIEWPORT_HARDENING_STYLESHEET" in source
    assert "_inject_runtime_viewport_hardening" in source
    assert "runtime_viewport_hardening.css" in source
