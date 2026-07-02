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

    assert "MAESTRO ADMIN" in html
    assert "Admin Area" in html
    assert "verifyAdmin" in html
    assert "CLIENT.get('/auth/me')" in html
    assert "role !== 'admin'" in html
    assert "window.location.replace('/login?mode=admin')" in html


def test_admin_shell_is_not_pricing_or_checkout() -> None:
    html = ADMIN_HTML.read_text(encoding="utf-8").lower()

    assert "stripe" not in html
    assert "checkout" not in html
    assert "/pricing" not in html
