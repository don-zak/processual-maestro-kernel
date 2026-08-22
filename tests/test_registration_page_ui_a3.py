from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.main import app

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"


def test_registration_page_is_available() -> None:
    client = TestClient(app)

    response = client.get("/register")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_registration_page_contains_accessible_form_contract() -> None:
    html = (STATIC / "register.html").read_text(encoding="utf-8")

    assert 'id="registration-form"' in html
    assert 'name="email"' in html
    assert 'name="password"' in html
    assert 'type="email"' in html
    assert 'type="password"' in html
    assert 'aria-live="polite"' in html
    assert 'href="/login"' in html
    assert 'href="/plans"' in html


def test_registration_page_loads_controller() -> None:
    html = (STATIC / "register.html").read_text(encoding="utf-8")

    assert "/console/js/pages/register.js" in html


def test_registration_controller_uses_server_config_and_safe_response() -> None:
    javascript = (STATIC / "js" / "pages" / "register.js").read_text(encoding="utf-8")

    assert "registration/config" in javascript
    assert "registration" in javascript
    assert "Registration request accepted" in javascript

    submit_start = javascript.index("async function submitRegistration")
    submit_end = javascript.index("modeFieldset.addEventListener", submit_start)
    submit_source = javascript[submit_start:submit_end]
    assert "innerHTML" not in submit_source
    assert "setStatus(" in submit_source
    assert "response.json()" in submit_source
