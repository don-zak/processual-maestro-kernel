from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_console_first_response_rewrites_legacy_demo_state() -> None:
    middleware = _text("processual_api/middleware/security_headers.py")

    assert '(b"Demo Mode", b"Qualification Ready")' in middleware
    assert 'path in {"/", "/console", "/console/", "/console/index.html"}' in middleware
    assert "_rewrite_public_authority_claims" in middleware
    assert '"no-store, no-cache, must-revalidate, max-age=0"' in middleware


def test_login_first_response_contains_password_visibility_control() -> None:
    middleware = _text("processual_api/middleware/security_headers.py")

    assert "_LOGIN_PASSWORD_FIRST_PAINT" in middleware
    assert 'id=\\"login-password-visibility\\"' in middleware
    assert "_stabilize_login_first_paint" in middleware
    assert 'if path == "/login"' in middleware
    assert 'response.headers["Clear-Site-Data"] = \'"cache"\'' in middleware


def test_button_audit_v2_and_quiet_local_runtime_are_required() -> None:
    audit_script = _text("scripts/check_button_actions.ps1")
    run_script = _text("scripts/run_local_review.ps1")
    workflow = _text(".github/workflows/vq1-browser-qualification.yml")
    validator = _text("qualification/vq1_button_action_validator_v2.py")

    assert "vq1_button_action_validator_v2.py" in audit_script
    assert "=== SAVED BUTTON ACTION REPORT ===" in audit_script
    assert "ConvertFrom-Json" in audit_script
    assert "--no-access-log" in run_script
    assert "vq1_button_action_validator_v2.py" in workflow
    assert "establish_qualification_session" in validator
    assert "=== BUTTON ACTION AUDIT SUMMARY ===" in validator
    assert "write_fatal_report" in validator
