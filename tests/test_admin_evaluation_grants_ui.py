from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
SUMMARY_SCRIPT = JS / "admin_api_key_summary.js"
MANAGEMENT_SCRIPT = JS / "admin_evaluation_grants.js"
SESSION_SCRIPT = JS / "admin_session.js"


def _summary_source() -> str:
    return SUMMARY_SCRIPT.read_text(encoding="utf-8")


def _management_source() -> str:
    return MANAGEMENT_SCRIPT.read_text(encoding="utf-8")


def _session_source() -> str:
    return SESSION_SCRIPT.read_text(encoding="utf-8")


def test_admin_api_key_area_exposes_evaluation_grant_controls() -> None:
    source = _management_source()

    required = [
        "External Evaluation Access",
        "/settings/admin/evaluation-grants",
        "Create Evaluation Grant",
        "Issue API Key",
        "Revoke",
        "subscription required: no",
        "production: disabled",
    ]
    for marker in required:
        assert marker in source


def test_evaluation_grant_ui_selects_from_canonical_task_catalog() -> None:
    source = _management_source()

    required = [
        "/settings/admin/evaluation-grants/task-catalog",
        "API key task content",
        "canonical Maestro task catalog",
        "data-eval-task",
        "selectedEvaluationTasks",
        "allowed_task_ids",
        "Bound tasks:",
        "task_authority_source",
    ]
    for marker in required:
        assert marker in source


def test_evaluation_grant_ui_uses_admin_auth_and_one_time_secret_boundary() -> None:
    source = _management_source()

    assert "window.PMK_ADMIN_AUTH" in source
    assert "credentials: 'include'" in source
    assert "X-API-Key:" in source
    assert "Copy it now; it will not be displayed again." in source
    assert "key_hash" not in source
    assert "provider_secret" not in source


def test_evaluation_grant_ui_requires_at_least_one_task() -> None:
    source = _management_source()

    assert "Select at least one canonical task for the API key content." in source
    assert "if (!allowedTaskIds.length)" in source


def test_lifecycle_summary_stays_read_only_and_does_not_load_management() -> None:
    source = _summary_source()

    assert "pmk-evaluation-grant-updated" in source
    assert "method: 'GET'" in source
    assert "method: 'POST'" not in source
    assert "method: 'DELETE'" not in source
    assert "admin_evaluation_grants.js" not in source
    assert "dataset.adminEvaluationGrants" not in source


def test_admin_session_gates_evaluation_management_on_verified_authority() -> None:
    source = _session_source()

    required = [
        "fetch('/auth/me'",
        "canManageEvaluationGrants",
        "EVALUATION_ADMIN_ROLES",
        "owner_admin",
        "security_admin",
        "billing_admin",
        "admin:api_keys:write",
        "admin_evaluation_grants.js",
        "dataset.adminEvaluationGrants",
        "document.body.dataset.adminEvaluationGrants = 'authorized'",
        "document.body.dataset.adminEvaluationGrants = 'not-authorized'",
    ]
    for marker in required:
        assert marker in source

    assert source.index("if (!isAdminSession(me))") < source.index(
        "if (canManageEvaluationGrants(me))"
    )
    assert source.index("if (canManageEvaluationGrants(me))") < source.index(
        "loadEvaluationGrantControls();"
    )


def test_admin_session_retries_only_transient_503_with_bounded_backoff() -> None:
    source = _session_source()

    assert "const SESSION_RETRY_DELAYS_MS = [400, 1200, 2500]" in source
    assert "response.status !== 503" in source
    assert "for (const delayMs of SESSION_RETRY_DELAYS_MS)" in source
    assert "document.body.dataset.adminSession = 'retrying-503'" in source
    assert "document.body.dataset.adminEvaluationGrants = 'auth-retrying'" in source
    assert "Retrying safely..." in source
    assert "while (" not in source


def test_verified_admin_session_emits_single_bootstrap_event() -> None:
    source = _session_source()

    assert "function dispatchAdminSessionVerified(me)" in source
    assert "pmk-admin-session-verified" in source
    assert source.index("document.body.dataset.adminSession = 'ok'") < source.index(
        "dispatchAdminSessionVerified(me);"
    )


def test_evaluation_access_card_is_visible_before_authority_check() -> None:
    source = _session_source()

    required = [
        "const EVALUATION_HOST_ID = 'admin-evaluation-grants'",
        "function ensureEvaluationGrantPlaceholder()",
        "External Evaluation Access",
        "Checking administrator authority for evaluation grant management...",
        "Backend scopes remain authoritative.",
        "Management controls appear only after verified authorization.",
        "ensureEvaluationGrantPlaceholder();\n  checkAdminSession();",
    ]
    for marker in required:
        assert marker in source


def test_evaluation_access_card_explains_non_authorized_states() -> None:
    source = _session_source()

    required = [
        "document.body.dataset.adminEvaluationGrants = 'auth-missing'",
        "Administrator credential is required before evaluation grant controls can be shown.",
        "document.body.dataset.adminEvaluationGrants = 'auth-error'",
        "Administrator verification failed: HTTP ",
        "The current session is authenticated but does not have administrator authority for this area.",
        "Administrator session verified, but evaluation grant management requires owner, security, billing, wildcard, or admin:api_keys:write authority.",
    ]
    for marker in required:
        assert marker in source


def test_local_development_evaluation_auth_bootstrap_is_session_only() -> None:
    source = _session_source()

    required = [
        "const EVALUATION_DEV_AUTH_ID = 'admin-evaluation-dev-auth'",
        "const LOCAL_DEVELOPMENT_HOSTS = new Set(['127.0.0.1', 'localhost', '::1'])",
        "function isLocalDevelopmentOrigin()",
        "function renderDevelopmentAuthBootstrap()",
        "type=\"password\"",
        "autocomplete=\"off\"",
        "sessionStorage.setItem('api_key', value)",
        "Verify & Load Controls",
        "await checkAdminSession();",
    ]
    for marker in required:
        assert marker in source

    assert "localStorage.setItem('api_key'" not in source
    assert source.index("if (!isLocalDevelopmentOrigin()) return;") < source.index(
        "sessionStorage.setItem('api_key', value)"
    )


def test_evaluation_management_loader_is_idempotent_and_reports_asset_failure() -> None:
    source = _session_source()

    assert "document.querySelector(EVALUATION_SCRIPT_SELECTOR)" in source
    assert "if (document.querySelector(EVALUATION_SCRIPT_SELECTOR)) return;" in source
    assert "script.addEventListener('error'" in source
    assert "setEvaluationAccessStatus(message, true)" in source
    assert "Evaluation grant controls could not be loaded." in source


def test_evaluation_ui_does_not_own_navigation_or_reload_behavior() -> None:
    source = _management_source()

    forbidden = [
        "location.reload",
        "location.replace",
        "location.assign",
        "window.location.href",
    ]
    for marker in forbidden:
        assert marker not in source


def test_api_key_ui_scripts_are_invoked() -> None:
    assert _summary_source().rstrip().endswith("})();")
    assert _management_source().rstrip().endswith("})();")
    assert _session_source().rstrip().endswith("});")
