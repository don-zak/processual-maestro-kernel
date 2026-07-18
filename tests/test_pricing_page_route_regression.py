from fastapi.testclient import TestClient

from processual_api.main import app


def test_pricing_page_route_serves_static_pricing_surface() -> None:
    response = TestClient(app).get("/pricing")

    assert response.status_code == 200
    assert "Subscription options" in response.text
    assert 'id="pricing-plan-grid"' in response.text
    assert 'loadJson("/billing/pricing-catalog")' in response.text


def test_pricing_html_route_alias_serves_static_pricing_surface() -> None:
    response = TestClient(app).get("/pricing.html")

    assert response.status_code == 200
    assert "Subscription options" in response.text


def test_login_links_to_public_pricing_route() -> None:
    response = TestClient(app).get("/login")

    assert response.status_code == 200
    assert 'href="/pricing"' in response.text
    assert 'href="/console/pricing.html"' not in response.text
