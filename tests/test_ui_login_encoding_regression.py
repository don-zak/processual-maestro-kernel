from pathlib import Path
import re


LOGIN_HTML = Path("processual_api/static/login.html")

BAD_MOJIBAKE_MARKERS = (
    "\u00c3",
    "\u00c2",
    "\u00e2\u20ac",
    "\u00e2\u20ac\u2122",
    "\ufffd",
)


def test_login_html_is_utf8_and_has_clean_title() -> None:
    text = LOGIN_HTML.read_text(encoding="utf-8")

    compact = re.sub(r"\s+", "", text.lower())
    assert '<metacharset="utf-8"/>' in compact or '<metacharset="utf-8">' in compact
    assert "<title>Maestro Kernel - Sign In</title>" in text


def test_login_html_contains_no_visible_mojibake_markers() -> None:
    text = LOGIN_HTML.read_text(encoding="utf-8")

    found = [marker for marker in BAD_MOJIBAKE_MARKERS if marker in text]
    assert found == []


def test_login_password_placeholder_is_ascii_safe() -> None:
    text = LOGIN_HTML.read_text(encoding="utf-8")

    assert 'id="login-password"' in text
    assert 'placeholder="********"' in text
