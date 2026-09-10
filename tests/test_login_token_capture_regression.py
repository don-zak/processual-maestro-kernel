from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_login_loads_identity_mfa_bridge_early() -> None:
    html = (STATIC_DIR / "login.html").read_text(encoding="utf-8")

    assert "/console/js/login_token_capture.js?v=identity-mfa-v1" in html
    assert html.index("login_token_capture.js") < html.index("</head>")


def test_login_shell_has_no_superseded_inline_auth_authority() -> None:
    html = (STATIC_DIR / "login.html").read_text(encoding="utf-8")

    for forbidden in (
        "fetch('/auth/token'",
        "async function doLogin",
        "PMK_LOGIN_TOKEN_CAPTURE",
        "persistAuthPayload",
        "sessionStorage.setItem('maestro_token'",
        "sessionStorage.setItem('maestro_role'",
    ):
        assert forbidden not in html
    assert "form.addEventListener('submit',(event)=>event.preventDefault());" in html


def test_login_bridge_persists_only_canonical_identity_session() -> None:
    script = (STATIC_DIR / "js" / "login_token_capture.js").read_text(encoding="utf-8")

    for required in (
        "persistIdentitySession",
        "sessionStorage.setItem('maestro_token', token)",
        "sessionStorage.setItem('maestro_role'",
        "PMK_LOGIN_IDENTITY",
        "/auth/login",
        "/auth/mfa/status",
        "/auth/mfa/totp/enroll",
        "/auth/mfa/totp/confirm",
        "/auth/mfa/verify",
        "/auth/session/refresh",
    ):
        assert required in script

    for forbidden in (
        "persistAuthPayload",
        "installFetchCapture",
        "loginTokenCapturingFetch",
        "PMK_LOGIN_TOKEN_CAPTURE_INSTALLED",
        "localStorage.setItem(",
        "localStorage.getItem(",
    ):
        assert forbidden not in script


def test_login_bridge_only_removes_legacy_token_copies() -> None:
    script = (STATIC_DIR / "js" / "login_token_capture.js").read_text(encoding="utf-8")

    assert "clearRestrictedTokenCopies" in script
    assert "localStorage.removeItem(key)" in script
    assert "sessionStorage.removeItem(key)" in script
    for legacy_key in (
        "'access_token'",
        "'auth_token'",
        "'admin_access_token'",
        "'admin_token'",
        "'admin_session'",
        "'processual_session'",
    ):
        assert legacy_key in script
