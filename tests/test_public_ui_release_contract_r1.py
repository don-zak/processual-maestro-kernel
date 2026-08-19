from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from processual_api.middleware.security_headers import SecurityHeadersMiddleware


ROOT = Path(__file__).resolve().parents[1]


def test_offer_to_registration_preserves_plan_and_billing_period() -> None:
    offer = (ROOT / "processual_api/static/js/pages/offer.js").read_text()
    registration = (ROOT / "processual_api/static/js/pages/register.js").read_text()
    service = (ROOT / "processual_api/auth/registration_service.py").read_text()

    assert "plan_id=${encodeURIComponent(plan.plan_id)}&billing_period=monthly" in offer
    assert "plan_id=${encodeURIComponent(plan.plan_id)}&billing_period=annual" in offer

    assert 'queryValue("plan_id")' in registration
    assert 'queryValue("billing_period")' in registration
    assert 'period === "monthly" || period === "annual"' in registration
    assert "payload.selected_plan_id = planId" in registration
    assert "payload.billing_period = selectedBillingPeriod()" in registration
    assert "This plan registration link is incomplete." in registration

    assert 'billing_period not in ("monthly", "annual")' in service
    assert "billing_period=billing_period" in service


def test_registration_page_has_accessible_responsive_baseline() -> None:
    html = (ROOT / "processual_api/static/register.html").read_text()

    assert 'name="viewport"' in html
    assert 'width=device-width, initial-scale=1' in html
    assert 'for="registration-full-name"' in html
    assert 'for="registration-email"' in html
    assert 'for="registration-password"' in html
    assert 'aria-describedby="password-requirements"' in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert ':focus-visible' in html
    assert 'nav aria-label="Registration links"' in html


def test_public_ui_delivery_rewrites_ungranted_production_claims() -> None:
    async def public_home(_request):
        return HTMLResponse('<footer>Production Ready · جاهز للإنتاج</footer>')

    async def console(_request):
        return HTMLResponse('<footer>v2.0.0 — production</footer>')

    app = Starlette(
        routes=[
            Route("/", public_home),
            Route("/console/", console),
        ]
    )
    app.add_middleware(SecurityHeadersMiddleware)

    with TestClient(app) as client:
        splash_response = client.get("/")
        console_response = client.get("/console/")

    assert splash_response.status_code == 200
    assert "Production Ready" not in splash_response.text
    assert "جاهز للإنتاج" not in splash_response.text
    assert "Qualification Build" in splash_response.text
    assert "نسخة تأهيل" in splash_response.text

    assert console_response.status_code == 200
    assert "v2.0.0 — production" not in console_response.text
    assert "v2.0.0 — qualification" in console_response.text


def test_browser_security_headers_cover_modern_baseline() -> None:
    async def health(_request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/health", health)])
    app.add_middleware(SecurityHeadersMiddleware)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-xss-protection"] == "0"
    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == (
        "camera=(), microphone=(), geolocation=(), payment=()"
    )

    csp = response.headers["content-security-policy"]
    for directive in (
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "upgrade-insecure-requests",
    ):
        assert directive in csp

    assert "*" not in csp
    assert "http:" not in csp
