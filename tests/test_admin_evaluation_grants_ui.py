from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
API_KEYS_SCRIPT = JS / "admin_api_keys.js"
SUMMARY_SCRIPT = JS / "admin_api_key_summary.js"
MANAGEMENT_SCRIPT = JS / "admin_evaluation_grants.js"
SESSION_SCRIPT = JS / "admin_session.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_admin_api_key_area_exposes_evaluation_grant_controls() -> None:
    source = _source(MANAGEMENT_SCRIPT)

    required = [
        "Evaluation Grant Preparation",
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
    source = _source(MANAGEMENT_SCRIPT)

    required = [
        "/settings/admin/evaluation-grants/task-catalog",
        "API key task content",
        "canonical tasks",
        "data-eval-task",
        "selectedEvaluationTasks",
        "allowed_task_ids",
        "Bound tasks:",
        "task_authority_source",
    ]
    for marker in required:
        assert marker in source


def test_evaluation_grant_ui_uses_admin_auth_and_one_time_secret_boundary() -> None:
    source = _source(MANAGEMENT_SCRIPT)

    assert "window.PMK_ADMIN_AUTH" in source
    assert "credentials: 'include'" in source
    assert "X-API-Key:" in source
    assert "Copy it now; it will not be displayed again." in source
    assert "sessionStorage.setItem" not in source
    assert "localStorage.setItem" not in source
    assert "key_hash" not in source


def test_lifecycle_summary_stays_read_only_and_not_an_owner() -> None:
    source = _source(SUMMARY_SCRIPT)

    assert "API Key Lifecycle Summary" in source
    assert "pmk-evaluation-grant-updated" in source
    assert "method: 'GET'" in source
    assert "method: 'POST'" not in source
    assert "method: 'DELETE'" not in source
    assert "ensureEvaluationCard" not in source
    assert "MutationObserver" not in source


def test_primary_renderer_owns_visible_external_evaluation_shell() -> None:
    source = _source(API_KEYS_SCRIPT)

    required = [
        "External Evaluation Lifecycle",
        "Administrator Verification",
        "Operational Profile & Eligible Endpoints",
        "Evaluation Access Preview",
        "admin-api-key-external-evaluation-card",
        "admin-api-key-external-evaluation-body",
        "admin-evaluation-grants",
    ]
    for marker in required:
        assert marker in source

    assert "Activate External Evaluation" not in source
    assert "External Evaluation Active" not in source


def test_admin_session_gates_management_on_verified_authority_without_dom_creation() -> None:
    source = _source(SESSION_SCRIPT)

    required = [
        "fetch('/auth/me'",
        "canManageEvaluationGrants",
        "EVALUATION_ADMIN_ROLES",
        "owner_admin",
        "security_admin",
        "billing_admin",
        "admin:api_keys:write",
        "admin_evaluation_grants.js",
        "document.body.dataset.adminEvaluationGrants = 'authorized'",
        "document.body.dataset.adminEvaluationGrants = 'not-authorized'",
        "window.PMK_ADMIN_SESSION",
    ]
    for marker in required:
        assert marker in source

    assert "ensureEvaluationGrantPlaceholder" not in source
    assert "admin-api-key-lifecycle-card" not in source
    assert "MutationObserver" not in source
    assert "insertBefore" not in source


def test_admin_session_retries_only_transient_503_with_bounded_backoff() -> None:
    source = _source(SESSION_SCRIPT)

    assert "const SESSION_RETRY_DELAYS_MS = [400, 1200, 2500]" in source
    assert "response.status !== 503" in source
    assert "for (const delayMs of SESSION_RETRY_DELAYS_MS)" in source
    assert "document.body.dataset.adminSession = 'retrying-503'" in source
    assert "document.body.dataset.adminEvaluationGrants = 'auth-retrying'" in source
    assert "Retrying safely..." in source
    assert "while (" not in source


def test_verified_admin_session_emits_bootstrap_event_before_privileged_modules() -> None:
    source = _source(SESSION_SCRIPT)

    assert "function dispatchAdminSessionVerified(me)" in source
    assert "pmk-admin-session-verified" in source
    assert source.index("document.body.dataset.adminSession = 'ok'") < source.index(
        "loadApiKeyProvisioningWorkspace();"
    )
    assert source.index("loadApiKeyProvisioningWorkspace();") < source.index(
        "dispatchAdminSessionVerified(me);"
    )


def test_evaluation_access_card_explains_non_authorized_states() -> None:
    source = _source(SESSION_SCRIPT)

    required = [
        "document.body.dataset.adminEvaluationGrants = 'auth-missing'",
        "Administrator credential is required before evaluation grant controls can be enabled.",
        "document.body.dataset.adminEvaluationGrants = 'auth-error'",
        "Administrator verification failed: HTTP ",
        "The current session is authenticated but does not have administrator authority for this area.",
        "Administrator session verified, but evaluation grant management requires owner, security, billing, wildcard, or admin:api_keys:write authority.",
    ]
    for marker in required:
        assert marker in source


def test_local_development_evaluation_auth_bootstrap_is_session_only_and_retryable() -> None:
    source = _source(SESSION_SCRIPT)

    required = [
        "const EVALUATION_DEV_AUTH_ID = 'admin-evaluation-dev-auth'",
        "const LOCAL_DEVELOPMENT_HOSTS = new Set(['127.0.0.1', 'localhost', '::1'])",
        "if (!isLocalDevelopmentOrigin() || !externalEvaluationSelected()) return;",
        "type=\"password\"",
        "autocomplete=\"off\"",
        "sessionStorage.setItem('api_key', value)",
        "Verify & Load Controls",
        "Credential was not accepted. Enter another development API key.",
        "response.status === 401 || response.status === 403",
    ]
    for marker in required:
        assert marker in source

    assert "localStorage.setItem('api_key'" not in source


def test_evaluation_management_loader_is_idempotent_and_reports_asset_failure() -> None:
    source = _source(SESSION_SCRIPT)

    assert "if (document.querySelector(EVALUATION_SCRIPT_SELECTOR)) return;" in source
    assert "script.addEventListener('error'" in source
    assert "Evaluation grant controls could not be loaded." in source


def test_category_change_rechecks_admin_without_loading_legacy_dom_mover() -> None:
    source = _source(SESSION_SCRIPT)

    assert "window.addEventListener('pmk-api-key-category-changed'" in source
    assert "if (externalEvaluationSelected())" in source
    assert "checkAdminSession();" in source
    assert "loadApiKeyProvisioningWorkspace();" in source
    assert "loadEvaluationGrantControls();" in source
    assert "admin_api_key_evaluation_lifecycle.js" not in source


def test_evaluation_ui_does_not_own_navigation_or_reload_behavior() -> None:
    source = _source(MANAGEMENT_SCRIPT)

    for marker in ["location.reload", "location.replace", "location.assign", "window.location.href"]:
        assert marker not in source
