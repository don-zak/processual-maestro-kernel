from fastapi import FastAPI
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


def test_admin_document_is_never_reused_from_stale_browser_cache() -> None:
    response = _client().get('/admin')

    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store, no-cache, must-revalidate, max-age=0'
    assert response.headers['pragma'] == 'no-cache'
    assert response.headers['expires'] == '0'


def test_admin_javascript_assets_are_never_reused_from_stale_browser_cache() -> None:
    response = _client().get('/console/js/admin_session.js?v=old-cache-key')

    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store, no-cache, must-revalidate, max-age=0'
    assert response.headers['pragma'] == 'no-cache'
    assert response.headers['expires'] == '0'


def test_non_admin_console_assets_keep_normal_cache_semantics() -> None:
    response = _client().get('/console/js/client.js')

    assert response.status_code == 200
    assert 'cache-control' not in response.headers
    assert 'pragma' not in response.headers
    assert 'expires' not in response.headers
