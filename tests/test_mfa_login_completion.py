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


def test_user_login_requires_mfa_completion_before_session_persistence() -> None:
    source = Path("processual_api/static/js/login_token_capture.js").read_text(encoding="utf-8")
    login_html = Path("processual_api/static/login.html").read_text(encoding="utf-8")

    assert "if (payload?.mfa_required === true) return false" in source
    assert "fetch('/auth/login'" in source
    assert "fetch('/auth/mfa/status'" in source
    assert "fetch('/auth/mfa/verify'" in source
    assert "fetch('/auth/mfa/totp/enroll'" in source
    assert "fetch('/auth/mfa/totp/confirm'" in source
    assert "fetch('/auth/session/refresh'" in source
    assert "'X-CSRF-Token':pendingCsrfToken" in source
    assert "data.mfa_required === true" in source
    assert "async function refreshAfterMfa()" in source
    assert "persistUserSession(token)" in source

    assert 'id="tab-admin"' in login_html
    assert 'id="tab-user"' in login_html
    assert "/console/js/login_token_capture.js" in login_html
    assert "role: currentRole" not in login_html


def test_identity_session_authority_is_mfa_aware() -> None:
    source = Path("processual_api/auth/security.py").read_text(encoding="utf-8")

    assert "mfa_pending = mfa_required and auth_session.mfa_satisfied_at is None" in source
    assert '"scopes": ["auth:mfa"] if mfa_pending else ["evaluation"]' in source
