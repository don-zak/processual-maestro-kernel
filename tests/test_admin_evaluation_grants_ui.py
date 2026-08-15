from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
API_KEYS_SCRIPT = JS / "admin_api_keys.js"
SUMMARY_SCRIPT = JS / "admin_api_key_summary.js"
MANAGEMENT_SCRIPT = JS / "admin_evaluation_grants.js"
SESSION_SCRIPT = JS / "admin_session.js"
PROVISIONING_SCRIPT = JS / "admin_api_key_provisioning_workspace.js"
EVALUATION_ROUTER = ROOT / "processual_api" / "routers" / "settings_admin_evaluation_grants.py"
PROVISIONING_ROUTER = ROOT / "processual_api" / "routers" / "settings_admin_api_key_provisioning.py"
SUPER_ADMIN_AUTHORITY = ROOT / "processual_api" / "auth" / "platform_admin_authority.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_admin_api_key_area_exposes_evaluation_grant_controls() -> None:
    source = _source(MANAGEMENT_SCRIPT)
    required = [
        "/settings/admin/evaluation-grants",
        "Create Evaluation Grant",
        "Issue API Key",
        "Revoke",
        "production disabled",
        "Canonical Tasks",
        "Evaluation Identity",
        "Duration / Quota",
        "Access Preview · Readiness",
    ]
    for marker in required:
        assert marker in source


def test_evaluation_grant_ui_selects_from_canonical_task_catalog() -> None:
    source = _source(MANAGEMENT_SCRIPT)
    required = [
        "/settings/admin/evaluation-grants/task-catalog",
        "canonical task",
        "data-eval-task",
        "selectedEvaluationTasks",
        "allowed_task_ids",
    ]
    for marker in required:
        assert marker in source


def test_evaluation_grant_ui_uses_admin_auth_and_one_time_secret_boundary() -> None:
    source = _source(MANAGEMENT_SCRIPT)
    assert "window.PMK_ADMIN_AUTH" in source
    assert "credentials: 'include'" in source
    assert "X-API-Key:" in source
    assert "Copy it now" in source
    assert "let oneTimeIssuedKey = ''" in source
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
        "Operational Profile",
        "Eligible Endpoints & Derived Runtime Scopes",
        "Canonical Tasks",
        "Evaluation Identity & Limits",
        "Access Preview & Readiness",
        "Create Grant & One-Time API Key",
        "Endpoint Test & Revocation",
        "admin-api-key-external-evaluation-card",
        "admin-api-key-external-evaluation-body",
        "admin-evaluation-grants",
    ]
    for marker in required:
        assert marker in source
    assert "Activate External Evaluation" not in source
    assert "External Evaluation Active" not in source


def test_session_uses_backend_super_admin_authority_probe_only() -> None:
    source = _source(SESSION_SCRIPT)
    required = [
        "const AUTHORITY_ENDPOINT = '/settings/admin/evaluation-grants/authority'",
        "fetch(AUTHORITY_ENDPOINT",
        "authority.authority !== 'platform_admin'",
        "authority.exclusive_super_administrator !== true",
        "document.body.dataset.adminEvaluationGrants = 'authorized'",
        "document.body.dataset.adminEvaluationGrants = 'not-authorized'",
        "window.PMK_ADMIN_SESSION",
        "owner_admin, security_admin, billing_admin, wildcard scopes, and API keys are not sufficient.",
    ]
    for marker in required:
        assert marker in source

    for forbidden in [
        "EVALUATION_ADMIN_ROLES",
        "canManageEvaluationGrants",
        "sessionStorage.setItem('api_key'",
        "EVALUATION_DEV_AUTH_ID",
        "fetch('/auth/me'",
    ]:
        assert forbidden not in source

    assert "ensureEvaluationGrantPlaceholder" not in source
    assert "admin-api-key-lifecycle-card" not in source
    assert "MutationObserver" not in source
    assert "insertBefore" not in source


def test_admin_session_preloads_locked_ui_before_super_admin_verification() -> None:
    source = _source(SESSION_SCRIPT)
    preload = source.rindex("loadApiKeyProvisioningWorkspace();")
    preload_grants = source.rindex("loadEvaluationGrantControls();")
    initial_check = source.rindex("checkAdminSession();")
    assert preload < initial_check
    assert preload_grants < initial_check
    assert "document.body.dataset.adminEvaluationUi = 'loaded'" in source
    assert "document.body.dataset.adminEvaluationGrants = 'loaded'" not in source


def test_super_admin_authority_is_set_before_hydration_event() -> None:
    source = _source(SESSION_SCRIPT)
    ok_pos = source.index("document.body.dataset.adminSession = 'ok'")
    authority_pos = source.index("document.body.dataset.adminEvaluationGrants = 'authorized'", ok_pos)
    event_pos = source.index("dispatchSuperAdminVerified(authority);", authority_pos)
    assert ok_pos < authority_pos < event_pos


def test_provisioning_renders_locked_shell_without_privileged_requests() -> None:
    source = _source(PROVISIONING_SCRIPT)
    assert "LOCKED — verify administrator first" in source
    assert "renderPreview();" in source
    assert "window.addEventListener('pmk-admin-session-verified', hydrateWorkspace)" in source
    hydrate_start = source.index("async function hydrateWorkspace()")
    init_start = source.index("function initializeWorkspace()")
    hydrate_source = source[hydrate_start:init_start]
    assert "document.body.dataset.adminSession !== 'ok'" in hydrate_source
    assert "loadOperationalProfiles()" in hydrate_source
    assert "loadAccessCatalog()" in hydrate_source


def test_grants_render_locked_shell_and_hydrate_only_when_authorized() -> None:
    source = _source(MANAGEMENT_SCRIPT)
    assert "function renderLockedShell()" in source
    assert "LOCKED — canonical task choices will load after administrator verification." in source
    assert "disabled>Create Evaluation Grant" in source
    assert "window.addEventListener('pmk-admin-session-verified', hydrateEvaluationControls)" in source
    assert "document.body.dataset.adminEvaluationGrants === 'authorized'" in source
    assert "document.body.dataset.adminEvaluationGrants === 'loaded'" not in source


def test_admin_session_retries_only_transient_503_with_bounded_backoff() -> None:
    source = _source(SESSION_SCRIPT)
    assert "const SESSION_RETRY_DELAYS_MS = [400, 1200, 2500]" in source
    assert "response.status !== 503" in source
    assert "for (const delayMs of SESSION_RETRY_DELAYS_MS)" in source
    assert "document.body.dataset.adminSession = 'retrying-503'" in source
    assert "Retrying safely..." in source
    assert "while (" not in source


def test_evaluation_access_card_explains_exclusive_super_admin_states() -> None:
    source = _source(SESSION_SCRIPT)
    required = [
        "Super Administrator identity session is required.",
        "External Evaluation is exclusive to an active Super Administrator (platform_admin).",
        "owner_admin, security_admin, billing_admin, wildcard scopes, and API keys are not sufficient.",
        "Backend did not confirm exclusive Super Administrator authority.",
    ]
    for marker in required:
        assert marker in source


def test_backend_evaluation_grants_require_platform_admin_helper_everywhere() -> None:
    source = _source(EVALUATION_ROUTER)
    assert "/admin/evaluation-grants/authority" in source
    assert "require_active_platform_admin" in source
    assert source.count("await require_active_platform_admin(current_user)") == 6
    assert "_ALLOWED_ADMIN_ROLES" not in source
    assert 'created_by_admin_role": "platform_admin"' in source
    assert '"exclusive_super_administrator": True' in source


def test_backend_provisioning_catalogs_are_super_admin_only() -> None:
    source = _source(PROVISIONING_ROUTER)
    assert source.count("await require_active_platform_admin(current_user)") == 2
    assert "_ALLOWED_ADMIN_ROLES" not in source
    assert "_ALLOWED_ADMIN_SCOPES" not in source
    assert source.count('"exclusive_super_administrator": True') == 2


def test_platform_admin_helper_rejects_legacy_and_non_identity_authority() -> None:
    source = _source(SUPER_ADMIN_AUTHORITY)
    required = [
        'SUPER_ADMIN_AUTHORITY = "platform_admin"',
        'current_user.get("session_type") != "identity_user"',
        "AdminMarketplaceIdentityAuthorityResolver",
        "authority.active_platform_admin",
        "SUPER_ADMIN_AUTHORITY not in authority.platform_authorities",
        "Exclusive super-administrator identity authority is required.",
    ]
    for marker in required:
        assert marker in source

    for forbidden in ["owner_admin", "security_admin", "billing_admin", "admin:*", "admin:api_keys:write"]:
        assert forbidden not in source


def test_primary_renderer_has_single_category_verification_trigger() -> None:
    api_keys = _source(API_KEYS_SCRIPT)
    session = _source(SESSION_SCRIPT)
    apply_start = api_keys.index("function applyLifecycleCategory()")
    defaults_start = api_keys.index("function applyCategoryDefaults()", apply_start)
    apply_source = api_keys[apply_start:defaults_start]
    assert "window.PMK_ADMIN_SESSION?.check?.();" in apply_source
    assert "dispatchCategoryChanged();" in apply_source
    assert "window.addEventListener('pmk-api-key-category-changed'" in session
    assert "admin_api_key_evaluation_lifecycle.js" not in session


def test_evaluation_ui_does_not_own_navigation_or_reload_behavior() -> None:
    source = _source(MANAGEMENT_SCRIPT)
    for marker in ["location.reload", "location.replace", "location.assign", "window.location.href"]:
        assert marker not in source
