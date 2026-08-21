from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.main import app

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_assessment_only_offer_links_to_supported_public_application_page():
    source = read("processual_api/static/js/pages/offer.js")

    assert "/console/apply.html?plan_id=${encodeURIComponent(plan.plan_id)}&journey=assessment" in source
    assert "assessment.href = `/apply?" not in source


def test_public_application_page_is_served_by_static_mount():
    response = TestClient(app).get(
        "/console/apply.html?plan_id=enterprise_integration_starter&journey=assessment"
    )

    assert response.status_code == 200
    assert "Request a Maestro assessment" in response.text
    assert "No payment, quota, subscription, or production entitlement" in response.text
    assert 'fetch("/applications"' in response.text
    assert 'preferred_plan: selectedPlan.plan_id' in response.text


def test_application_page_fails_closed_for_non_assessment_plan_client_side():
    source = read("processual_api/static/apply.html")

    assert "!selectedPlan.requires_assessment || selectedPlan.registration_available" in source
    assert "This assessment path is not available for the selected public offer." in source


def test_full_web_review_uses_actual_verification_and_application_routes():
    source = read("scripts/run_full_web_review.ps1")

    assert 'Path = "/verify-email"' in source
    assert 'Path = "/verify"' not in source
    assert 'Path = "/apply"' not in source
    assert '/console/apply.html?plan_id=$encodedPlan&journey=assessment' in source
    assert 'if ($plan.requires_assessment -or -not $plan.registration_available)' in source
