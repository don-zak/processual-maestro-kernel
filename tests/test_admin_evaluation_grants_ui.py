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
    for marker in (
        "Evaluation Grant Preparation",
        "/settings/admin/evaluation-grants",
        "Create Evaluation Grant",
        "Issue API Key",
        "Revoke",
        "subscription required: no",
        "production: disabled",
    ):
        assert marker in source


def test_evaluation_grant_ui_selects_from_canonical_task_catalog() -> None:
    source = _management_source()
    for marker in (
        "/settings/admin/evaluation-grants/task-catalog",
        "API key task content",
        "canonical tasks",
        "data-eval-task",
        "selectedEvaluationTasks",
        "allowed_task_ids",
        "Tasks:",
        "task_authority_source",
    ):
        assert marker in source


def test_evaluation_grant_ui_uses_admin_auth_and_one_time_secret_boundary() -> None:
    source = _management_source()
    assert "window.PMK_ADMIN_AUTH" in source
    assert "credentials: 'include'" in source
    assert "X-API-Key:" in source
    assert "One-time Evaluation API key created." in source
    assert "Copy the secret now; it will not be displayed again." in source
    assert "approved secret-delivery channel separately from the safe handoff text" in source
    assert "Safe customer handoff" in source
    assert "Copy customer handoff" in source
    assert "navigator.clipboard.writeText(secret)" in source
    assert "navigator.clipboard.writeText(safeHandoff)" in source
    assert "key_hash" not in source
    assert "provider_secret" not in source


def test_evaluation_grant_ui_requires_at_least_one_task() -> None:
    source = _management_source()
    assert "tasks.length > 0" in source
    assert "Select at least one canonical task." in source
    assert "button.disabled = !readiness.ready" in source
    assert "if (!readiness.ready)" in source


def test_lifecycle_summary_stays_read_only_and_does_not_load_management() -> None:
    source = _summary_source()
    assert "pmk-evaluation-grant-updated" in source
    assert "method: 'GET'" in source
    assert "method: 'POST'" not in source
    assert "method: 'DELETE'" not in source
    assert "admin_evaluation_grants.js" not in source
    assert "dataset.adminEvaluationGrants" not in source


def test_admin_session_gates_evaluation_management_on_platform_admin_authority() -> None:
    source = _session_source()
    for marker in (
        "const AUTHORITY_ENDPOINT = '/settings/admin/evaluation-grants/authority'",
        "verifyPlatformAdminAuthority",
        "authority?.authorized !== true",
        "authority?.authority !== 'platform_admin'",
        "document.body.dataset.adminEvaluationGrants = 'authorized'",
        "document.body.dataset.adminEvaluationGrants = 'not-authorized'",
        "loadProtectedEvaluationControls();",
    ):
        assert marker in source
    assert "canManageEvaluationGrants" not in source
    assert "EVALUATION_ADMIN_ROLES" not in source
    assert "owner_admin" not in source
    assert "billing_admin" not in source


def test_admin_session_retries_only_transient_503_with_bounded_backoff() -> None:
    source = _session_source()
    assert "const SESSION_RETRY_DELAYS_MS = [400, 1200, 2500]" in source
    assert "response.status !== 503" in source
    assert "for (const delayMs of SESSION_RETRY_DELAYS_MS)" in source
    assert "document.body.dataset.adminSession = 'retrying-503'" in source
    assert "while (" not in source


def test_verified_admin_session_emits_platform_admin_bootstrap_event() -> None:
    source = _session_source()
    assert "function dispatchAdminSessionVerified(authority)" in source
    assert "pmk-admin-session-verified" in source
    assert "authority: authority.authority || 'platform_admin'" in source
    assert source.index("document.body.dataset.adminSession = 'ok'") < source.index(
        "dispatchAdminSessionVerified(authority);"
    )


def test_evaluation_access_surface_is_category_driven_without_legacy_activation() -> None:
    source = _session_source()
    for marker in (
        "const API_KEY_LIFECYCLE_CARD_ID = 'admin-api-key-lifecycle-card'",
        "const EVALUATION_CARD_ID = 'admin-api-key-external-evaluation-card'",
        "const EVALUATION_HOST_ID = 'admin-evaluation-grants'",
        "function ensureEvaluationGrantPlaceholder()",
        "External Evaluation Authority",
        "PostgreSQL-backed Evaluation authority is authoritative",
        "syncEvaluationSelectionState();",
    ):
        assert marker in source
    assert "if (!lifecycleCard) return null" in source
    assert "lifecycleCard.insertBefore(card, lifecycleForm)" in source
    assert "Activate External Evaluation" not in source
    assert "External Evaluation Active" not in source
    assert "EVALUATION_ACTIVATE_ID" not in source
    assert "fallback-page" not in source


def test_evaluation_access_card_explains_non_authorized_states() -> None:
    source = _session_source()
    for marker in (
        "document.body.dataset.adminEvaluationGrants = 'auth-missing'",
        "Active administrator Identity session required",
        "document.body.dataset.adminEvaluationGrants = 'authority-unavailable'",
        "Platform Administrator authority unavailable",
        "Authenticated identity does not hold active Platform Administrator authority.",
        "Administrator session expired. Sign in again and complete MFA",
    ):
        assert marker in source


def test_admin_session_refresh_is_single_flight_and_mfa_fail_closed() -> None:
    source = _session_source()
    for marker in (
        "const SESSION_REFRESH_ENDPOINT = '/auth/session/refresh'",
        "const CSRF_COOKIE = 'pmk_csrf_token'",
        "if (refreshInFlight) return refreshInFlight",
        "'X-CSRF-Token': csrf",
        "if (payload?.mfa_required === true) return false",
        "sessionStorage.setItem('maestro_token', token)",
        "if (response.status === 401)",
        "if (response.status === 401 || response.status === 403)",
        "markSessionExpired(response.status)",
    ):
        assert marker in source


def test_admin_authority_verification_is_single_flight_and_short_lived_cached() -> None:
    source = _session_source()
    for marker in (
        "const AUTHORITY_VERIFICATION_TTL_MS = 1500",
        "let authorityCheckInFlight = null",
        "let lastVerifiedBearer = ''",
        "let lastAuthorityVerifiedAt = 0",
        "if (authorityCheckInFlight) return authorityCheckInFlight",
        "authorityCheckInFlight = runAdminSessionCheck(token)",
        "token === lastVerifiedBearer",
        "Date.now() - lastAuthorityVerifiedAt < AUTHORITY_VERIFICATION_TTL_MS",
        "lastVerifiedBearer = token",
        "lastAuthorityVerifiedAt = Date.now()",
        "resetAuthorityVerificationCache();",
    ):
        assert marker in source


def test_evaluation_management_loader_is_idempotent_and_reports_asset_failure() -> None:
    source = _session_source()
    assert "function loadScript(selector, src, datasetKey, onLoad)" in source
    assert "if (document.querySelector(selector))" in source
    assert "script.addEventListener('error'" in source
    assert "Protected Evaluation asset failed to load" in source


def test_category_change_rechecks_authority_and_loads_evaluation_controls() -> None:
    source = _session_source()
    assert "window.addEventListener('pmk-api-key-category-changed'" in source
    assert "syncEvaluationSelectionState();" in source
    assert "await checkAdminSession();" in source
    assert "loadProtectedEvaluationControls();" in source


def test_evaluation_ui_does_not_own_navigation_or_reload_behavior() -> None:
    source = _management_source()
    for marker in ("location.reload", "location.replace", "location.assign", "window.location.href"):
        assert marker not in source


def test_api_key_ui_scripts_are_invoked() -> None:
    assert _summary_source().rstrip().endswith("})();")
    assert _management_source().rstrip().endswith("})();")
    assert _session_source().rstrip().endswith("});")
