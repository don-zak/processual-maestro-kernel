from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from processual_api.middleware.security_headers import SecurityHeadersMiddleware


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get('/admin')
    async def admin_page():
        return {'ok': True}

    @app.get('/console/js/admin_session.js')
    async def admin_session_asset():
        return {'asset': 'admin-session'}

    @app.get('/console/js/client.js')
    async def client_asset():
        return {'asset': 'client'}

    return TestClient(app)


def _html_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get('/admin', response_class=HTMLResponse)
    async def admin_page():
        return '<html><body><main>admin</main></body></html>'

    return TestClient(app)


def _assert_no_store(response) -> None:
    assert response.headers['cache-control'] == 'no-store, no-cache, must-revalidate, max-age=0'
    assert response.headers['pragma'] == 'no-cache'
    assert response.headers['expires'] == '0'


def test_admin_document_is_never_reused_from_stale_browser_cache() -> None:
    response = _client().get('/admin')

    assert response.status_code == 200
    _assert_no_store(response)


def test_admin_javascript_assets_are_never_reused_from_stale_browser_cache() -> None:
    response = _client().get('/console/js/admin_session.js?v=old-cache-key')

    assert response.status_code == 200
    _assert_no_store(response)


def test_all_console_assets_follow_no_store_security_boundary() -> None:
    response = _client().get('/console/js/client.js')

    assert response.status_code == 200
    _assert_no_store(response)


def test_admin_html_always_loads_external_evaluation_dom_contract() -> None:
    response = _html_client().get('/admin')

    assert response.status_code == 200
    assert (
        '<script src="/console/js/admin_external_evaluation_dom_contract.js?'
        'v=admindomcontract01"></script>'
    ) in response.text
    assert response.text.count('admin_external_evaluation_dom_contract.js') == 1
