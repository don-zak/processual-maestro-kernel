from fastapi.testclient import TestClient

from processual_api.main import app

client = TestClient(app)


def test_legacy_pricing_catalog_contract_is_preserved() -> None:
    response = client.get("/billing/pricing-catalog")
    assert response.status_code == 200
    payload = response.json()
    assert payload["pricing_status"] == "draft"
    assert all(plan.get("monthly_price_usd") is None for plan in payload["plans"])


def test_group2_commercial_catalog_is_separate_and_fail_closed() -> None:
    response = client.get("/billing/commercial-pricing-catalog")
    assert response.status_code == 200
    payload = response.json()
    assert payload["pricing_status"] == "draft_review"
    assert payload["checkout_enabled"] is False
    assert payload["plans"][0]["plan_id"] == "academic"
    assert len(payload["plans"]) == 8


def test_pricing_page_uses_group2_catalog_route() -> None:
    text = open("processual_api/static/pricing.html", encoding="utf-8").read()
    assert 'loadJson("/billing/commercial-pricing-catalog")' in text
    assert 'loadJson("/billing/pricing-catalog")' in text
    assert ".catch(() =>" in text


def test_login_baseline_markers_and_alignment_assets_coexist() -> None:
    text = open("processual_api/static/login.html", encoding="utf-8").read()
    assert 'data-ar="العروض والتسجيل"' in text
    assert "auth_commercial_alignment_group2.css?v=2" in text
    assert "auth_commercial_alignment_group2.js?v=2" in text
    assert "Ã" not in text
    assert "Â" not in text
    assert "â€" not in text


def test_group2_single_plan_catalog_route_is_fail_closed() -> None:
    response = client.get("/billing/commercial-pricing-catalog/starter")
    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["plan_id"] == "starter"
    assert payload["checkout_enabled"] is False
    assert payload["plan"]["purchasable"] is False


def test_group2_single_plan_catalog_route_returns_404() -> None:
    response = client.get("/billing/commercial-pricing-catalog/not-a-plan")
    assert response.status_code == 404


def test_plan_detail_page_route_is_available() -> None:
    response = client.get("/plans/starter")
    assert response.status_code == 200
    assert 'id="plan-content"' in response.text
