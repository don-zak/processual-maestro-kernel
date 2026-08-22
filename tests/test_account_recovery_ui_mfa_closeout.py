from pathlib import Path


LOGIN_RUNTIME = Path("processual_api/static/js/login_token_capture.js")
RECOVERY_PAGE = Path("processual_api/static/recover-account.html")
DELIVERY_DISPATCHER = Path("processual_api/auth/delivery_dispatcher.py")
SESSION_REPOSITORY = Path("processual_api/auth/session_repository.py")
ACCOUNT_RECOVERY_SERVICE = Path("processual_api/auth/account_recovery_service.py")


def test_lost_access_starts_generic_server_side_account_recovery() -> None:
    source = LOGIN_RUNTIME.read_text(encoding="utf-8")

    assert "function installLostAccessRecovery()" in source
    assert "'/auth/account-recovery/start'" in source
    assert "JSON.stringify({login:input.value.trim()})" in source
    assert "If the account is eligible" in source
    assert "never reveals whether an account exists" in source
    assert "Do not send passwords, MFA codes, recovery codes, or API keys" in source


def test_recovery_email_opens_browser_page_not_post_only_api_route() -> None:
    source = DELIVERY_DISPATCHER.read_text(encoding="utf-8")

    assert 'verification_path="/console/recover-account.html"' in source
    assert 'verification_path="/auth/account-recovery/verify"' not in source


def test_recovery_browser_page_verifies_then_completes_without_session_authority() -> None:
    html = RECOVERY_PAGE.read_text(encoding="utf-8")

    assert "'/auth/account-recovery/verify'" in html
    assert "'/auth/account-recovery/complete'" in html
    assert "history.replaceState(null, '', '/console/recover-account.html')" in html
    assert "result.authority_granted !== false" in html
    assert "result.mfa_reenrollment_required !== true" in html
    assert "No session or account authority is created during recovery" in html
    assert "/login?mode=user&recovered=1" in html


def test_completed_recovery_remains_an_mfa_requirement_after_old_factor_revocation() -> None:
    source = SESSION_REPOSITORY.read_text(encoding="utf-8")

    assert "AuthAccountRecoveryRequest" in source
    assert 'AuthAccountRecoveryRequest.state == "completed"' in source
    assert "or completed_recovery_id is not None" in source


def test_login_mfa_flow_enrolls_when_factor_is_missing_and_verifies_when_present() -> None:
    source = LOGIN_RUNTIME.read_text(encoding="utf-8")

    assert "async function startMfaFlow()" in source
    assert "'/auth/mfa/status'" in source
    assert "if (data.enabled === true) showMfaChallenge()" in source
    assert "else await showMfaEnrollment()" in source
    assert "'/auth/mfa/totp/enroll'" in source
    assert "'/auth/mfa/totp/confirm'" in source
    assert "Array.isArray(data.recovery_codes)" in source
    assert "I saved the codes — Continue" in source
    assert "await refreshAfterMfa()" in source


def test_recovery_completion_revokes_old_authority_and_old_mfa_material() -> None:
    source = ACCOUNT_RECOVERY_SERVICE.read_text(encoding="utf-8")

    assert "revoke_refresh_tokens" in source
    assert "revoke_sessions" in source
    assert "invalidate_action_tokens" in source
    assert "disable_mfa_factors" in source
    assert "delete_mfa_recovery_codes" in source
    assert "supervisor_session_keys_revoked" in source
    assert "api_keys_revoked" in source
    assert "session_created=False" in source
    assert "access_token_issued=False" in source
    assert "authority_granted=False" in source
