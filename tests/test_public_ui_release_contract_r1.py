from __future__ import annotations

from pathlib import Path


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
    assert "payload.billing_period = billingPeriod" in registration

    assert 'billing_period not in ("monthly", "annual")' in service
    assert "billing_period=billing_period" in service


def test_public_ui_delivery_rewrites_ungranted_production_claims() -> None:
    middleware = (
        ROOT / "processual_api/middleware/security_headers.py"
    ).read_text()

    assert 'b"Production Ready", b"Qualification Build"' in middleware
    assert '"جاهز للإنتاج".encode(), "نسخة تأهيل".encode()' in middleware
    assert 'b"v2.0.0 \\xe2\\x80\\x94 production"' in middleware
    assert 'b"v2.0.0 \\xe2\\x80\\x94 qualification"' in middleware
    assert 'path in {"/", "/console", "/console/", "/console/index.html"}' in middleware


def test_browser_security_headers_cover_modern_baseline() -> None:
    middleware = (
        ROOT / "processual_api/middleware/security_headers.py"
    ).read_text()

    assert 'response.headers["X-Content-Type-Options"] = "nosniff"' in middleware
    assert 'response.headers["X-Frame-Options"] = "DENY"' in middleware
    assert 'response.headers["Strict-Transport-Security"]' in middleware
    assert 'response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"' in middleware
    assert 'response.headers["Permissions-Policy"]' in middleware
    assert 'camera=(), microphone=(), geolocation=(), payment=()' in middleware
