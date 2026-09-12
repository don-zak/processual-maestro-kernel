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

    assert "fetch('/auth/login'" in source
    assert "fetch('/auth/mfa/verify'" in source
    assert "fetch('/auth/session/refresh'" in source
    assert "'X-CSRF-Token': pendingCsrfToken" in source
    assert "if (refreshedData.mfa_required === true)" in source
    assert "persistIdentitySession(token, pendingEntryMode)" in source
    assert "event.stopImmediatePropagation();" in source

    assert "persistAuthPayload" not in source
    assert "loginTokenCapturingFetch" not in source
    assert "installFetchCapture" not in source


def test_platform_admin_login_uses_identity_session_and_mfa_onboarding() -> None:
    source = Path("processual_api/static/js/login_token_capture.js").read_text(encoding="utf-8")

    assert "const currentEntryMode = () => isUserMode() ? 'user' : 'admin';" in source
    assert "pendingEntryMode = currentEntryMode();" in source
    assert "fetch('/auth/mfa/status'" in source
    assert "fetch('/auth/mfa/totp/enroll'" in source
    assert "fetch('/auth/mfa/totp/confirm'" in source
    assert "status.enabled === true" in source
    assert "status.pending_enrollment === true" in source
    assert "Maestro Platform Admin" in source
    assert "window.location.href = pendingEntryMode === 'admin' ? '/admin' : '/console';" in source


def test_platform_admin_identity_token_is_session_scoped_not_local_admin_token() -> None:
    source = Path("processual_api/static/js/login_token_capture.js").read_text(encoding="utf-8")
    identity_block = source.split("function persistIdentitySession", 1)[1].split(
        "const isUserMode", 1
    )[0]

    assert "sessionStorage.setItem('maestro_token', token);" in identity_block
    assert "sessionStorage.setItem('maestro_role', entryMode === 'admin' ? 'admin' : 'user');" in identity_block
    assert "localStorage.setItem" not in identity_block
    assert "admin_access_token" not in identity_block
    assert "admin_token" not in identity_block


def test_legacy_fetch_capture_is_fully_neutralized() -> None:
    source = Path("processual_api/static/js/login_token_capture.js").read_text(encoding="utf-8")

    for marker in (
        "function shouldCapture",
        "function installFetchCapture",
        "loginTokenCapturingFetch",
        "PMK_LOGIN_TOKEN_CAPTURE_INSTALLED",
        "persistAuthPayload",
        "window.fetch =",
    ):
        assert marker not in source


def test_mfa_enrollment_material_and_recovery_codes_are_not_persisted() -> None:
    source = Path("processual_api/static/js/login_token_capture.js").read_text(encoding="utf-8")

    assert "data.secret" in source
    assert "data.provisioning_uri" in source
    assert "codes.join('\\n')" in source
    assert "secret.value = '';" in source
    assert "uri.value = '';" in source

    persistence_block = source.split("function persistIdentitySession", 1)[1].split(
        "const isUserMode", 1
    )[0]
    assert "recovery_codes" not in persistence_block
    assert "provisioning_uri" not in persistence_block
    assert "identity-mfa-secret" not in persistence_block


def test_identity_session_authority_is_mfa_aware() -> None:
    source = Path("processual_api/auth/security_legacy.py").read_text(encoding="utf-8")

    assert "mfa_pending = mfa_required and auth_session.mfa_satisfied_at is None" in source
    assert '"scopes": ["auth:mfa"] if mfa_pending else ["evaluation"]' in source
