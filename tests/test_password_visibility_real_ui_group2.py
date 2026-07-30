from pathlib import Path

LOGIN = Path("processual_api/static/login.html")
REGISTER = Path("processual_api/static/register.html")
SCRIPT = Path("processual_api/static/js/auth_commercial_alignment_group2.js")
STYLE = Path("processual_api/static/css/auth_commercial_alignment_group2.css")


def test_login_uses_cache_busted_alignment_assets() -> None:
    text = LOGIN.read_text(encoding="utf-8")

    assert "auth_commercial_alignment_group2.css?v=2" in text
    assert "auth_commercial_alignment_group2.js?v=2" in text


def test_registration_uses_cache_busted_alignment_assets() -> None:
    text = REGISTER.read_text(encoding="utf-8")

    assert "auth_commercial_alignment_group2.css?v=2" in text
    assert "auth_commercial_alignment_group2.js?v=2" in text


def test_password_toggle_scans_dynamic_fields() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "MutationObserver" in text
    assert "scanPasswordFields" in text
    assert 'input[type="password"]' in text
    assert "window.setTimeout(refresh, 1000)" in text


def test_password_toggle_is_visible_and_accessible() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    style = STYLE.read_text(encoding="utf-8")

    assert 'button.type = "button"' in script
    assert "aria-pressed" in script
    assert "Show password" in script
    assert "Hide password" in script
    assert "setSelectionRange" in script
    assert "z-index: 20" in style
    assert "visibility: visible" in style
    assert "opacity: 1" in style
