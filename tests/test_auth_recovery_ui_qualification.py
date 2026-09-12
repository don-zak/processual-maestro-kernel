from pathlib import Path
import re

from processual_api.auth.account_recovery_router import router


STATIC = Path("processual_api/static")
ARABIC = re.compile(r"[\u0600-\u06ff]")
ROOT_OVERFLOW_HIDDEN = re.compile(r"(?:html|body)\s*\{[^}]*overflow\s*:\s*hidden", re.IGNORECASE | re.DOTALL)


def test_login_is_english_only_and_lost_access_enters_real_recovery_flow() -> None:
    html = (STATIC / "login.html").read_text(encoding="utf-8")
    login_js = (STATIC / "js" / "login_token_capture.js").read_text(encoding="utf-8")

    assert '<html lang="en" dir="ltr">' in html
    assert "lang-bar" not in html
    assert "data-ar" not in html
    assert 'data-lang="ar"' not in html
    assert "lang-ar" not in login_js
    assert "currentLanguage" not in login_js
    assert ARABIC.search(html) is None
    assert ARABIC.search(login_js) is None
    assert "login-password-visibility" in html
    assert "aria-pressed" in html
    assert "aria-selected" in html
    assert "aria-live=\"assertive\"" in html
    assert "prefers-reduced-motion" in html
    assert "fetch('/auth/token'" not in html
    assert "role: currentRole" not in html
    assert "fetch('/auth/login'" in login_js
    assert "fetch('/auth/mfa/status'" in login_js
    assert "fetch('/auth/session/refresh'" in login_js
    assert "persistIdentitySession" in login_js
    assert 'href="/console/account-recovery.html"' in html
    assert "Lost Access?" in html
    assert "Contact your administrator or support contact" not in html
    assert ROOT_OVERFLOW_HIDDEN.search(html) is None


def test_recovery_page_uses_hardened_three_step_contract_without_browser_storage() -> None:
    html = (STATIC / "account-recovery.html").read_text(encoding="utf-8")

    assert "fetch('/auth/account-recovery/start'" in html
    assert "fetch('/auth/account-recovery/verify'" in html
    assert "fetch('/auth/account-recovery/complete'" in html
    assert "history.replaceState(null,'',window.location.pathname)" in html
    assert "localStorage" not in html
    assert "sessionStorage" not in html
    assert 'autocomplete="new-password"' in html
    assert "MFA re-enrollment is required" in html
    assert "does not sign you in or grant new authority" in html
    assert "1. Request" in html
    assert "2. Verify" in html
    assert "3. Reset" in html
    assert "overflow-y:auto" in html
    assert ROOT_OVERFLOW_HIDDEN.search(html) is None
    assert "aria-live=\"polite\"" in html
    assert "aria-live=\"assertive\"" in html
    assert "prefers-reduced-motion" in html
    assert "fragment.get('token')||query.get('token')" in html
    assert "fragment.get('request_id')||query.get('request_id')" in html


def test_email_recovery_link_has_a_get_browser_handoff_alongside_post_verification() -> None:
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
