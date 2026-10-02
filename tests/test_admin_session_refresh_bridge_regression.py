from pathlib import Path


ADMIN_SESSION = Path("processual_api/static/js/admin_session.js")
SESSION_ROUTER = Path("processual_api/auth/session_router.py")


def test_admin_authority_check_attempts_single_identity_refresh_on_401() -> None:
    source = ADMIN_SESSION.read_text(encoding="utf-8")

    assert "const SESSION_REFRESH_ENDPOINT = '/auth/session/refresh'" in source
    assert "const CSRF_COOKIE = 'pmk_csrf_token'" in source
    assert "if (response.status === 401)" in source
    assert "const refreshed = await refreshIdentitySession()" in source
    assert "if (refreshed) response = await verifyPlatformAdminAuthority()" in source
    assert "let refreshInFlight = null" in source
    assert "payload?.mfa_required === true" in source


def test_csrf_cookie_is_browser_visible_but_refresh_cookie_stays_restricted() -> None:
    source = SESSION_ROUTER.read_text(encoding="utf-8")

    refresh_cookie_block = source.split("response.set_cookie(\n        REFRESH_COOKIE", 1)[1].split(")\n    response.set_cookie", 1)[0]
    csrf_cookie_block = source.split("response.set_cookie(\n        CSRF_COOKIE", 1)[1].split(")\n    response.headers", 1)[0]

    assert 'httponly=True' in refresh_cookie_block
    assert 'path="/auth/session"' in refresh_cookie_block
    assert 'httponly=False' in csrf_cookie_block
    assert 'samesite="strict"' in csrf_cookie_block
    assert 'path="/"' in csrf_cookie_block


def test_refresh_still_requires_double_submit_csrf() -> None:
    source = SESSION_ROUTER.read_text(encoding="utf-8")

    assert "secrets.compare_digest(csrf_cookie, supplied)" in source
    assert 'status_code=403, detail="Session request denied."' in source
