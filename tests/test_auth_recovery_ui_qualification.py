from pathlib import Path

from processual_api.auth.account_recovery_router import router


STATIC = Path("processual_api/static")


def test_login_is_english_only_and_lost_access_enters_real_recovery_flow() -> None:
    html = (STATIC / "login.html").read_text(encoding="utf-8")

    assert '<html lang="en" dir="ltr">' in html
    assert "lang-bar" not in html
    assert "data-ar" not in html
    assert 'data-lang="ar"' not in html
    assert "login-password-visibility" in html
    assert 'href="/console/account-recovery.html"' in html
    assert "Lost Access?" in html
    assert "Contact your administrator or support contact" not in html


def test_recovery_page_uses_hardened_three_step_contract_without_browser_storage() -> None:
    html = (STATIC / "account-recovery.html").read_text(encoding="utf-8")

    assert "fetch('/auth/account-recovery/start'" in html
    assert "fetch('/auth/account-recovery/verify'" in html
    assert "fetch('/auth/account-recovery/complete'" in html
    assert "history.replaceState(null, '', window.location.pathname)" in html
    assert "localStorage" not in html
    assert "sessionStorage" not in html
    assert 'autocomplete="new-password"' in html
    assert "MFA re-enrollment is required" in html
    assert "Recovery does not create a session or grant authority" in html


def test_email_recovery_link_has_a_get_browser_handoff_alongside_post_verification() -> None:
    methods_by_path = {
        route.path: route.methods
        for route in router.routes
        if getattr(route, "methods", None)
    }

    # FastAPI stores GET and POST as separate routes at the same path.
    matching = [
        route.methods
        for route in router.routes
        if route.path == "/auth/account-recovery/verify"
    ]
    assert any("GET" in methods for methods in matching)
    assert any("POST" in methods for methods in matching)


def test_recovery_browser_handoff_is_not_an_authority_action() -> None:
    matching = [
        route
        for route in router.routes
        if route.path == "/auth/account-recovery/verify" and "GET" in route.methods
    ]
    assert len(matching) == 1
    assert matching[0].include_in_schema is False
