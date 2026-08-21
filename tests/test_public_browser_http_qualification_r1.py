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

QUARANTINED_LEGACY_ASSETS = (
    "/console/js/adapters/governor.js",
    "/console/js/adapters/cgt.js",
    "/console/js/pages/governor.js",
    "/console/js/pages/cgt.js",
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
    assert "نسخة تأهيل" not in splash.text
    assert 'id="lang-ar"' not in splash.text
    assert 'data-lang="ar"' not in splash.text

    assert console.status_code == 200
    assert "v2.0.0 — production" not in console.text
    assert "v2.0.0 — qualification" in console.text


def test_console_delivers_pinned_chartjs_asset() -> None:
    response = client.get("/console/")

    assert response.status_code == 200
    assert "https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js" in response.text
    assert '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>' not in response.text


def test_legacy_raw_math_console_surfaces_are_quarantined_from_delivery() -> None:
    response = client.get("/console/")

    assert response.status_code == 200
    assert 'src="js/adapters/governor.js"' not in response.text
    assert 'src="js/adapters/cgt.js"' not in response.text
    assert 'src="js/pages/governor.js"' not in response.text
    assert 'src="js/pages/cgt.js"' not in response.text
    assert 'id="legacy-console-quarantine"' in response.text
    assert '[data-page="cgt"],[data-page="governor"]' in response.text
    assert '#page-cgt,#page-governor{display:none!important}' in response.text


def test_quarantined_legacy_assets_return_gone() -> None:
    for path in QUARANTINED_LEGACY_ASSETS:
        response = client.get(path)
        assert response.status_code == 410, path
        assert response.text == "legacy_console_surface_quarantined", path
        assert response.headers["x-content-type-options"] == "nosniff", path
        assert "object-src 'none'" in response.headers["content-security-policy"], path


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
