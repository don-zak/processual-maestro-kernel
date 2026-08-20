from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from processual_api.middleware.security_headers import SecurityHeadersMiddleware


async def _login(_request):
    return HTMLResponse(
        '<div class="inp-group">'
        '<input id="login-password" class="inp" type="password" '
        'placeholder="********" autocomplete="current-password">'
        '</div>'
    )


async def _console(_request):
    return HTMLResponse(
        '<html><body><span id="demo-badge">Demo Mode</span>'
        '<div class="v">v2.0.0 — production</div></body></html>'
    )


def _client() -> TestClient:
    app = Starlette(
        routes=[
            Route("/login", _login),
            Route("/console/", _console),
        ]
    )
    app.add_middleware(SecurityHeadersMiddleware)
    return TestClient(app)


def test_login_first_response_has_password_button_without_reload() -> None:
    with _client() as client:
        response = client.get("/login")

    assert response.status_code == 200
    assert 'id="login-password-visibility"' in response.text
    assert response.text.count('id="login-password-visibility"') == 1
    assert response.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    assert response.headers["clear-site-data"] == '"cache"'


def test_console_first_response_has_no_legacy_demo_or_production_badge() -> None:
    with _client() as client:
        response = client.get("/console/")

    assert response.status_code == 200
    assert "Qualification Ready" in response.text
    assert "Demo Mode" not in response.text
    assert "v2.0.0 — qualification" in response.text
    assert "v2.0.0 — production" not in response.text
    assert response.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
