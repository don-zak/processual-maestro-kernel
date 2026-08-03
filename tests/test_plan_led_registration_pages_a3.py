from fastapi.testclient import TestClient

from processual_api.main import app

client = TestClient(app)


def test_plans_page_is_public() -> None:
    response = client.get("/plans")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_plans_page_loads_server_owned_catalog() -> None:
    response = client.get("/plans")

    assert response.status_code == 200
    assert "/billing/public-plan-journey" in response.text


def test_plan_selection_page_does_not_embed_prices() -> None:
    response = client.get("/plans")

    assert response.status_code == 200
    assert "$29" not in response.text
    assert "$49" not in response.text
    assert "$519" not in response.text
    assert "$2,790" not in response.text


def test_offer_page_is_public() -> None:
    response = client.get("/offer/starter")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_offer_page_loads_selected_plan_from_server_catalog() -> None:
    response = client.get("/offer/starter")

    assert response.status_code == 200
    assert "/billing/public-plan-journey" in response.text


def test_unknown_offer_page_remains_safe() -> None:
    response = client.get("/offer/not-a-real-plan")

    assert response.status_code in {200, 404}
    assert "2790" not in response.text
