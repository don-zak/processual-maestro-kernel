import json
from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.billing.maestro_group1_selected_pricing import (
    DEFAULT_YEARLY_DISCOUNT_PERCENT,
)
from processual_api.main import app

ROOT = Path(__file__).resolve().parents[1]
PLANS_HTML = ROOT / "processual_api" / "static" / "plans.html"
PLANS_JS = ROOT / "processual_api" / "static" / "js" / "pages" / "plans.js"
OFFER_JS = ROOT / "processual_api" / "static" / "js" / "pages" / "offer.js"

RETIRED_IDS = {
    "enterprise_pilot",
    "enterprise_core",
    "enterprise_scale",
    "enterprise_strategic",
}
RETIRED_LABELS = {
    "Enterprise Pilot",
    "Enterprise Core",
    "Enterprise Scale",
    "Enterprise Strategic",
}


def _get(path: str) -> dict:
    response = TestClient(app).get(path)
    assert response.status_code == 200
    return response.json()


def test_all_public_commercial_endpoints_quarantine_retired_enterprise_tiers() -> None:
    payloads = [
        _get("/billing/public-plan-journey"),
        _get("/billing/pricing-catalog"),
        _get("/billing/offer-pricebook"),
    ]

    for payload in payloads:
        serialized = json.dumps(payload)
        lowered = serialized.lower()
        for retired in RETIRED_IDS:
            assert retired not in lowered
        for label in RETIRED_LABELS:
            assert label not in serialized


def test_public_plan_journey_has_exactly_two_enterprise_stages() -> None:
    payload = _get("/billing/public-plan-journey")
    enterprise = [plan for plan in payload["plans"] if plan["plan_id"].startswith("enterprise_")]

    assert [plan["plan_id"] for plan in enterprise] == [
        "enterprise_integration_starter",
        "enterprise_deployment",
    ]
    assert [plan["display_name"] for plan in enterprise] == [
        "Enterprise Integration Trial",
        "Enterprise Deployment",
    ]


def test_enterprise_trial_is_one_month_scope_limited_and_has_no_fixed_price() -> None:
    payload = _get("/billing/public-plan-journey")
    trial = next(plan for plan in payload["plans"] if plan["plan_id"] == "enterprise_integration_starter")

    assert trial["commercial_model"] == "requirements_based_evaluation"
    assert trial["trial"]["duration_days"] == 30
    assert trial["trial"]["termination_policy"] == "30_days_or_agreed_quota_exhausted"
    assert trial["included_quota_units"] is None
    assert trial["monthly_price_usd"] is None
    assert trial["annual_price_usd"] is None
    assert trial["fixed_public_price"] is False


def test_enterprise_deployment_has_no_generic_trial_price_or_quota() -> None:
    payload = _get("/billing/public-plan-journey")
    deployment = next(plan for plan in payload["plans"] if plan["plan_id"] == "enterprise_deployment")

    assert deployment["commercial_model"] == "requirements_based_contract"
    assert deployment["trial"]["duration_days"] is None
    assert deployment["included_quota_units"] is None
    assert deployment["monthly_price_usd"] is None
    assert deployment["annual_price_usd"] is None
    assert deployment["fixed_public_price"] is False


def test_public_offer_pricebook_never_leaks_enterprise_internal_amounts() -> None:
    payload = _get("/billing/offer-pricebook")
    enterprise = [offer for offer in payload["offers"] if offer["plan_id"].startswith("enterprise_")]

    assert {offer["plan_id"] for offer in enterprise} == {
        "enterprise_integration_starter",
        "enterprise_deployment",
    }
    for offer in enterprise:
        assert offer["billing_interval"] == "contact"
        assert offer["amount_cents"] is None
        assert offer["monthly_amount_cents"] is None
        assert offer["annual_amount_cents"] is None
        assert offer["usage_overage_unit_price_cents"] is None
        assert offer["monthly_unit_allowance"] is None
        assert offer["custom_quote_required"] is True
        assert offer["checkout_enabled"] is False


def test_annual_discount_has_one_authoritative_value_and_no_hard_coded_ui_percentage() -> None:
    journey = _get("/billing/public-plan-journey")
    html = PLANS_HTML.read_text(encoding="utf-8")
    plans_js = PLANS_JS.read_text(encoding="utf-8")
    offer_js = OFFER_JS.read_text(encoding="utf-8")

    assert journey["annual_discount_percent"] == int(DEFAULT_YEARLY_DISCOUNT_PERCENT) == 15
    assert "20%" not in html
    assert "15%" not in html
    assert "save 20%" not in plans_js.lower()
    assert "save 15%" not in plans_js.lower()
    assert "save 20%" not in offer_js.lower()
    assert "save 15%" not in offer_js.lower()
    assert "annual_discount_percent" in plans_js
    assert "annual_discount_percent" in offer_js


def test_public_offer_and_plan_scripts_use_current_enterprise_language_only() -> None:
    source = "\n".join(
        [
            PLANS_HTML.read_text(encoding="utf-8"),
            PLANS_JS.read_text(encoding="utf-8"),
            OFFER_JS.read_text(encoding="utf-8"),
        ]
    )

    for label in RETIRED_LABELS:
        assert label not in source
    assert "requirements-based" in source
    assert "one-month" in source.lower() or "one month" in source.lower()
