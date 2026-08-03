from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.main import app

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"


def test_email_verification_page_is_available() -> None:
    client = TestClient(app)

    response = client.get("/verify-email")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_email_verification_page_declares_distinct_states() -> None:
    html = (STATIC / "verify-email.html").read_text(encoding="utf-8")

    for state in (
        "pending",
        "processing",
        "verified",
        "invalid",
        "expired",
        "already-used",
        "rate-limited",
        "unavailable",
    ):
        assert f'data-verification-state="{state}"' in html

    assert 'aria-live="polite"' in html
    assert 'href="/login"' in html
    assert 'href="/pricing"' in html


def test_email_verification_page_loads_controller() -> None:
    html = (STATIC / "verify-email.html").read_text(encoding="utf-8")

    assert "/console/js/pages/verify-email.js" in html


def test_email_verification_controller_does_not_render_server_html() -> None:
    javascript = (STATIC / "js" / "pages" / "verify-email.js").read_text(encoding="utf-8")

    assert "URLSearchParams" in javascript
    assert "verification" in javascript
    assert "textContent" in javascript
    assert "innerHTML" not in javascript
