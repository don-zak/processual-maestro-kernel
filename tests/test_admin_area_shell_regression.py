from pathlib import Path

MAIN_PY = Path("processual_api/main.py")
LOGIN_HTML = Path("processual_api/static/login.html")
ADMIN_HTML = Path("processual_api/static/admin.html")


def test_admin_route_is_served_separately_from_console() -> None:
    source = MAIN_PY.read_text(encoding="utf-8")

    assert '_admin_path = Path(__file__).resolve().parent / "static" / "admin.html"' in source
    assert '@app.get("/admin"' in source
    assert "async def admin_page()" in source
    assert "return HTMLResponse(content=_admin_html)" in source


def test_login_routes_admin_to_admin_and_user_to_console() -> None:
    source = LOGIN_HTML.read_text(encoding="utf-8")

    assert "currentRole === 'admin' ? '/admin' : '/console'" in source
    assert "JSON.stringify({ username: user, password: pass, role: currentRole })" in source


def test_admin_shell_exists_and_checks_admin_session() -> None:
    html = ADMIN_HTML.read_text(encoding="utf-8")
    session_script = (
        ADMIN_HTML.parent / "js" / "admin_session.js"
    ).read_text(encoding="utf-8")
    nav_script = (
        ADMIN_HTML.parent / "js" / "admin_nav.js"
    ).read_text(encoding="utf-8")

    assert "MAESTRO ADMIN" in html
    assert "Admin Area" in html

    assert "js/admin_session.js" in html
    assert "js/admin_nav.js" in html
    assert "js/auth.js" not in html
    assert "/console/js/auth.js" not in html
    assert "AUTH.init()" not in html

    assert "fetch('/auth/me'" in session_script
    assert "role === 'admin'" in session_script
    assert "admin:settings" in session_script
    assert "PMK_ADMIN_AUTH.headers" in session_script
    assert "window.location.replace('/')" not in session_script

    assert "setActivePage" in nav_script
    assert "page-admin-home" in nav_script
    assert "page-admin-adapters" in nav_script
    assert "page-admin-api-keys" in nav_script
    assert "page-admin-clients" in nav_script
    assert "page-admin-usage" in nav_script
    assert "page-admin-program-progress" in nav_script
    assert "page-admin-system-health" in nav_script

def test_admin_shell_is_not_pricing_or_checkout() -> None:
    html = ADMIN_HTML.read_text(encoding="utf-8").lower()

    assert "stripe" not in html
    assert "checkout" not in html
    assert "/pricing" not in html
