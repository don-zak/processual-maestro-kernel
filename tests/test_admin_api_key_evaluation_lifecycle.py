from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
API_KEYS = JS / "admin_api_keys.js"
SESSION = JS / "admin_session.js"
PROVISIONING = JS / "admin_api_key_provisioning_workspace.js"
EVALUATION = JS / "admin_evaluation_grants.js"
LEGACY_LIFECYCLE = JS / "admin_api_key_evaluation_lifecycle.js"
DOM_CONTRACT = JS / "admin_external_evaluation_dom_contract.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_primary_renderer_owns_external_evaluation_category_and_surfaces() -> None:
    source = _source(API_KEYS)
    required = [
        "const EXTERNAL_CATEGORY = 'external_evaluation'",
        "External Evaluation Access - governed sandbox evaluation",
        "admin-api-key-category-surface",
        "admin-api-key-standard-lifecycle",
        "admin-api-key-external-evaluation-card",
        "admin-api-key-external-evaluation-body",
        "function applyLifecycleCategory()",
        "standard.hidden = external",
        "evaluation.hidden = !external",
        "evaluationBody.hidden = !external",
        "categorySelect?.addEventListener('change', applyCategoryDefaults)",
    ]
    for marker in required:
        assert marker in source


def test_complete_external_evaluation_stage_map_is_visible_from_renderer() -> None:
    source = _source(API_KEYS)
    stages = [
        "1. Administrator Verification",
        "2. Operational Profile",
        "3. Eligible Endpoints & Derived Runtime Scopes",
        "4. Canonical Tasks",
        "5. Evaluation Identity & Limits",
        "6. Access Preview & Readiness",
        "7. Create Grant & One-Time API Key",
        "8. Endpoint Test & Revocation",
    ]
    for stage in stages:
        assert stage in source
    assert "All lifecycle stages remain visible before verification" in source
    assert "LOCKED" in source


def test_verification_and_grant_hosts_are_separate_fixed_renderer_surfaces() -> None:
    source = _source(API_KEYS)
    assert "admin-evaluation-verification-controls" in source
    assert "admin-evaluation-grants" in source
    assert "admin-api-key-evaluation-verification-stage" in source
    assert "admin-api-key-evaluation-grant-stage" in source
    assert "small verification stage; it never owns the rest of the lifecycle" in source


def test_external_evaluation_has_no_legacy_activation_or_secondary_mode() -> None:
    api_keys = _source(API_KEYS)
    provisioning = _source(PROVISIONING)
    combined = api_keys + provisioning
    assert "Activate External Evaluation" not in combined
    assert "External Evaluation Active" not in combined
    assert "admin-api-key-provisioning-mode" not in provisioning
    assert "Standard / Integration Key" not in provisioning


def test_primary_renderer_hard_blocks_standard_key_creation_for_evaluation() -> None:
    source = _source(API_KEYS)
    create_start = source.index("async function createKey()")
    revoke_start = source.index("async function revokeKey", create_start)
    create_source = source[create_start:revoke_start]
    assert "selectedCategory() === EXTERNAL_CATEGORY" in create_source
    assert "Standard API key generation is blocked for External Evaluation." in create_source
    assert "return;" in create_source
    assert create_source.index("return;") < create_source.index("request('POST', '/settings/api-keys'")


def test_session_uses_renderer_verification_host_without_lifecycle_dom_ownership() -> None:
    source = _source(SESSION)
    assert "const VERIFICATION_HOST_ID = 'admin-evaluation-verification-controls'" in source
    assert "function evaluationHost()" in source
    assert "document.getElementById(VERIFICATION_HOST_ID)" in source
    assert "renderSuperAdminSignInAction" in source
    assert "Sign in as Super Administrator" in source
    assert "document.createElement('section')" not in source
    assert "ensureEvaluationGrantPlaceholder" not in source
    assert "admin-api-key-lifecycle-card" not in source
    assert "page.appendChild(host)" not in source
    assert "insertBefore" not in source
    assert "MutationObserver" not in source


def test_legacy_dom_owner_files_are_removed() -> None:
    assert not LEGACY_LIFECYCLE.exists()
    assert not DOM_CONTRACT.exists()


def test_provisioning_mounts_into_fixed_renderer_slot_without_reparenting() -> None:
    source = _source(PROVISIONING)
    required = [
        "const WORKSPACE_ID = 'admin-api-key-external-provisioning-slot'",
        "document.getElementById(WORKSPACE_ID)",
        "Operational Profile",
        "Eligible Endpoints",
        "Derived Runtime Scopes",
        "Backend Route Inventory",
        "Access Preview",
    ]
    for marker in required:
        assert marker in source
    assert "appendChild(workspace)" not in source
    assert "before(workspace)" not in source
    assert "insertBefore" not in source
    assert "MutationObserver" not in source


def test_operational_profile_is_intent_only_and_endpoints_derive_scopes() -> None:
    source = _source(PROVISIONING)
    assert "Choosing a profile does not mutate runtime scopes" in source
    assert "selectedEndpointScopes" in source
    assert "syncScopesFromEndpointSelection" in source
    assert "derivedScopes.join('\\n')" in source
    assert "profile.allowed_scopes" in source
    assert "target.value = profile" not in source
    assert "target.value = allowed.join" not in source


def test_session_preloads_locked_modules_then_unlocks_only_after_super_admin_probe() -> None:
    source = _source(SESSION)
    assert "const AUTHORITY_ENDPOINT = '/settings/admin/evaluation-grants/authority'" in source
    assert "loadApiKeyProvisioningWorkspace();" in source
    assert "loadEvaluationGrantControls();" in source
    assert "authority.authority !== 'platform_admin'" in source
    assert "authority.exclusive_super_administrator !== true" in source
    assert "document.body.dataset.adminSession = 'ok'" in source
    assert "document.body.dataset.adminEvaluationGrants = 'authorized'" in source
    assert "dispatchSuperAdminVerified(authority);" in source
    assert "admin_api_key_evaluation_lifecycle.js" not in source


def test_local_development_api_key_cannot_unlock_external_evaluation() -> None:
    source = _source(SESSION)
    assert "sessionStorage.setItem('api_key'" not in source
    assert "EVALUATION_DEV_AUTH_ID" not in source
    assert "Development API key" not in source
    assert "API keys and legacy admin sessions cannot unlock External Evaluation." in source


def test_evaluation_readiness_remains_hard_gated_and_non_bypassable() -> None:
    source = _source(EVALUATION)
    required = [
        "function evaluationReadiness()",
        "category === EXTERNAL_CATEGORY",
        "document.body.dataset.adminSession === 'ok'",
        "Boolean(profile)",
        "endpoints.length > 0",
        "scopes.length > 0",
        "tasks.length > 0",
        "purpose.length >= 10",
        "duration >= 1 && duration <= 90",
        "quota >= 1 && quota <= 10000",
        "button.disabled = !readiness.ready",
        "const readiness = updateEvaluationReadiness();",
        "if (!readiness.ready)",
    ]
    for marker in required:
        assert marker in source


def test_evaluation_authority_is_the_only_create_issue_revoke_path() -> None:
    source = _source(EVALUATION)
    assert "const EVALUATION_GRANTS_ENDPOINT = '/settings/admin/evaluation-grants'" in source
    assert "EVALUATION_GRANTS_ENDPOINT, 'POST'" in source
    assert "/issue-key" in source
    assert "'DELETE'" in source
    assert "/settings/api-keys" not in source


def test_evaluation_key_is_one_time_and_never_persisted() -> None:
    source = _source(EVALUATION)
    assert "One-time evaluation API key created." in source
    assert "Copy it now; it will not be displayed again after this result changes." in source
    assert "navigator.clipboard.writeText(secret)" in source
    assert "let oneTimeIssuedKey = ''" in source
    assert "sessionStorage.setItem" not in source
    assert "localStorage.setItem" not in source
