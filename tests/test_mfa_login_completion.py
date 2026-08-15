from pathlib import Path


def test_session_refresh_preserves_mfa_gate_contract() -> None:
    source = Path("processual_api/auth/session_service.py").read_text(encoding="utf-8")

    assert "await repository.requires_mfa(user.id)" in source
    assert "auth_session.mfa_satisfied_at is None" in source
    assert "mfa_required=mfa_required" in source
    assert 'scopes=["auth:mfa"] if mfa_required else ["evaluation"]' in source


def test_identity_login_router_exposes_completion_material() -> None:
    source = Path("processual_api/auth/session_router.py").read_text(encoding="utf-8")

    assert "csrf_token=issued.csrf_token" in source
    assert "mfa_required=True if issued.mfa_required else None" in source
    assert source.count("csrf_token=issued.csrf_token") >= 2


def test_identity_login_requires_mfa_completion_before_session_persistence() -> None:
    source = Path("processual_api/static/js/login_token_capture.js").read_text(encoding="utf-8")
    login_html = Path("processual_api/static/login.html").read_text(encoding="utf-8")

    assert "if (payload?.mfa_required === true) return false" in source
    assert "fetch('/auth/login'" in source
    assert "fetch('/auth/mfa/status'" in source
    assert "fetch('/auth/mfa/verify'" in source
    assert "fetch('/auth/session/refresh'" in source
    assert "'X-CSRF-Token': pendingCsrfToken" in source
    assert "if (data.mfa_required === true)" in source
    assert "persistIdentitySession(token)" in source

    assert "fetch('/auth/token'" in login_html
    assert "role: currentRole" in login_html


def test_first_identity_login_can_enroll_totp_and_shows_recovery_codes_once() -> None:
    source = Path("processual_api/static/js/login_token_capture.js").read_text(encoding="utf-8")

    required = [
        "fetch('/auth/mfa/totp/enroll'",
        "fetch('/auth/mfa/totp/confirm'",
        "identity-mfa-enrollment-secret",
        "identity-mfa-enrollment-uri",
        "identity-mfa-recovery-code-list",
        "Recovery codes — shown once",
        "They are not saved in browser storage.",
        "completedIdentityToken",
        "function clearMfaEnrollmentMaterial()",
        "if (secret) secret.textContent = ''",
        "if (uri) uri.textContent = ''",
        "clearMfaEnrollmentMaterial();",
    ]
    for marker in required:
        assert marker in source

    assert "localStorage.setItem('identity-mfa" not in source
    assert "sessionStorage.setItem('identity-mfa" not in source


def test_super_admin_identity_login_uses_admin_tab_and_real_identity_endpoint() -> None:
    source = Path("processual_api/static/js/login_token_capture.js").read_text(encoding="utf-8")
    admin_session = Path("processual_api/static/js/admin_session.js").read_text(encoding="utf-8")

    assert "function explicitSuperAdminMode()" in source
    assert "params.get('identity') === '1' && params.get('mode') === 'admin'" in source
    assert "const isIdentityMode = () => isUserMode() || explicitSuperAdminMode();" in source
    assert "if (!isIdentityMode()) return;" in source
    assert "fetch('/auth/login'" in source
    assert 'href="/login?mode=admin&identity=1&next=%2Fadmin%23api-keys"' in admin_session
    assert "email/password + MFA flow" in admin_session


def test_identity_login_supports_safe_return_to_admin_api_keys() -> None:
    source = Path("processual_api/static/js/login_token_capture.js").read_text(encoding="utf-8")

    assert "function safeIdentityDestination()" in source
    assert "target.pathname !== '/admin' && target.pathname !== '/console'" in source
    assert "window.location.href = safeIdentityDestination();" in source
    assert "destination.startsWith('/admin') ? 'admin' : 'user'" in source
    assert "explicitSuperAdminMode() ? '/admin#api-keys' : '/console'" in source


def test_login_restores_password_visibility_control() -> None:
    source = Path("processual_api/static/js/login_token_capture.js").read_text(encoding="utf-8")

    required = [
        "function buildPasswordVisibilityToggle()",
        "login-password-visibility",
        "input.type = reveal ? 'text' : 'password'",
        "Show password",
        "Hide password",
        "buildPasswordVisibilityToggle();",
    ]
    for marker in required:
        assert marker in source


def test_super_admin_identity_mode_labels_username_field_as_email() -> None:
    source = Path("processual_api/static/js/login_token_capture.js").read_text(encoding="utf-8")

    assert "function syncIdentityModePresentation()" in source
    assert "username.placeholder = 'email@example.com'" in source
    assert "usernameLabel.textContent = message('Email', 'البريد الإلكتروني')" in source


def test_identity_session_authority_is_mfa_aware() -> None:
    source = Path("processual_api/auth/security.py").read_text(encoding="utf-8")

    assert "mfa_pending = mfa_required and auth_session.mfa_satisfied_at is None" in source
    assert '"scopes": ["auth:mfa"] if mfa_pending else ["evaluation"]' in source
