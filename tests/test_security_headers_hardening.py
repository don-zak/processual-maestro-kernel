from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from processual_api.middleware.security_headers import SecurityHeadersMiddleware


async def _json_ok(request):
    return JSONResponse({"ok": True})


async def _admin_html(request):
    return HTMLResponse("<html><body><main>admin</main></body></html>")


def _client() -> TestClient:
    app = Starlette(
        routes=[
            Route("/ok", _json_ok),
            Route("/admin", _admin_html),
        ]
    )
    app.add_middleware(SecurityHeadersMiddleware)
    return TestClient(app)


def test_browser_hardening_headers_are_applied_to_api_responses() -> None:
    response = _client().get("/ok")

    assert response.status_code == 200
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["x-permitted-cross-domain-policies"] == "none"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_admin_injection_preserves_hardening_and_no_store_headers() -> None:
    response = _client().get("/admin")

    assert response.status_code == 200
    assert "/console/js/admin_external_evaluation_dom_contract.js" in response.text
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["x-permitted-cross-domain-policies"] == "none"
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
