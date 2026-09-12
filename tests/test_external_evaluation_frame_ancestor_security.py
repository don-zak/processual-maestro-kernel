from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from processual_api.middleware.security_headers import SecurityHeadersMiddleware


async def _html(request):
    return HTMLResponse("<html><body>ok</body></html>")


def _client() -> TestClient:
    app = Starlette(
        routes=[
            Route("/console/evaluation.html", _html),
            Route("/console/evaluation-other.html", _html),
            Route("/console/js/evaluation_client_portal.js", _html),
        ]
    )
    app.add_middleware(SecurityHeadersMiddleware)
    return TestClient(app)


def test_only_external_evaluation_workspace_can_be_framed_by_zaxam() -> None:
    response = _client().get("/console/evaluation.html")

    assert response.status_code == 200
    assert "x-frame-options" not in response.headers
    assert response.headers["content-security-policy"] == "frame-ancestors https://zaxam.net"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"


def test_neighboring_console_routes_keep_global_frame_deny() -> None:
    for path in (
        "/console/evaluation-other.html",
        "/console/js/evaluation_client_portal.js",
    ):
        response = _client().get(path)
        assert response.status_code == 200
        assert response.headers["x-frame-options"] == "DENY"
        assert "content-security-policy" not in response.headers


def test_frame_policy_does_not_allow_wildcards_or_unrelated_origins() -> None:
    response = _client().get("/console/evaluation.html")
    policy = response.headers["content-security-policy"]

    assert "*" not in policy
    assert "github.io" not in policy
    assert "onrender.com" not in policy
    assert "http://" not in policy
    assert "https://zaxam.net" in policy
