from fastapi.testclient import TestClient

from processual_api.main import app


client = TestClient(app)


PUBLIC_HTML_ROUTES = (
    "/",
    "/login",
    "/plans",
    "/offer/starter",
    "/register",
    "/verify-email",
    "/pricing",
    "/console/",
)


def test_public_html_routes_render_with_browser_security_contract() -> None:
    for route in PUBLIC_HTML_ROUTES:
        response = client.get(route)

        assert response.status_code == 200, route
        assert "text/html" in response.headers.get("content-type", ""), route
        assert response.headers["x-content-type-options"] == "nosniff", route
        assert response.headers["x-frame-options"] == "DENY", route
        assert response.headers["x-xss-protection"] == "0", route
        assert response.headers["referrer-policy"] == (
            "strict-origin-when-cross-origin"
        ), route
        assert response.headers["permissions-policy"] == (
            "camera=(), microphone=(), geolocation=(), payment=()"
        ), route

        csp = response.headers["content-security-policy"]
        assert "default-src 'self'" in csp, route
        assert "object-src 'none'" in csp, route
        assert "frame-ancestors 'none'" in csp, route
        assert "form-action 'self'" in csp, route
        assert "*" not in csp, route


def test_public_entry_surfaces_do_not_deliver_ungranted_production_authority() -> None:
    splash = client.get("/")
    console = client.get("/console/")

    assert splash.status_code == 200
    assert "Production Ready" not in splash.text
    assert "جاهز للإنتاج" not in splash.text
    assert "Qualification Build" in splash.text
    assert "نسخة تأهيل" in splash.text

    assert console.status_code == 200
    assert "v2.0.0 — production" not in console.text
    assert "v2.0.0 — qualification" in console.text


def test_admin_rendered_response_keeps_no_store_and_dom_contract() -> None:
    response = client.get("/admin")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert response.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
    assert "/console/js/admin_external_evaluation_dom_contract.js" in response.text
    assert response.text.count("admin_external_evaluation_dom_contract.js") == 1
    assert "object-src 'none'" in response.headers["content-security-policy"]
