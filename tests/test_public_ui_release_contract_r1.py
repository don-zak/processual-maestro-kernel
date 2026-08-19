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


def test_public_ui_does_not_claim_ungranted_production_authority() -> None:
    splash = (ROOT / "processual_api/static/splash.html").read_text()
    console = (ROOT / "processual_api/static/index.html").read_text()

    for source in (splash, console):
        assert "Production Ready" not in source
        assert "جاهز للإنتاج" not in source

    assert "v2.0.0 — production" not in console
    assert "Qualification" in splash
    assert "qualification" in console.lower()
