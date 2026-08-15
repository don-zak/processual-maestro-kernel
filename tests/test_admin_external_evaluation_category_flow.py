from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
API_KEYS = JS / "admin_api_keys.js"
SUMMARY = JS / "admin_api_key_summary.js"
SESSION = JS / "admin_session.js"
PROVISIONING = JS / "admin_api_key_provisioning_workspace.js"
EVALUATION = JS / "admin_evaluation_grants.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_external_evaluation_is_declared_in_primary_key_categories() -> None:
    source = _source(API_KEYS)

    assert "const EXTERNAL_CATEGORY = 'external_evaluation'" in source
    assert "[EXTERNAL_CATEGORY, 'External Evaluation Access - governed sandbox evaluation']" in source
    assert "const KEY_CATEGORIES = [" in source


def test_primary_renderer_creates_both_lifecycle_surfaces_and_full_stage_map() -> None:
    source = _source(API_KEYS)

    required = [
        "admin-api-key-category-surface",
        "admin-api-key-standard-lifecycle",
        "admin-api-key-external-evaluation-card",
        "admin-api-key-external-evaluation-body",
        "Administrator Verification",
        "Operational Profile",
        "Eligible Endpoints & Derived Runtime Scopes",
        "Canonical Tasks",
        "Evaluation Identity & Limits",
        "Access Preview & Readiness",
        "Create Grant & One-Time API Key",
        "Endpoint Test & Revocation",
    ]
    for marker in required:
        assert marker in source


def test_category_selection_directly_switches_surfaces() -> None:
    source = _source(API_KEYS)

    start = source.index("function applyLifecycleCategory()")
    end = source.index("function applyCategoryDefaults()", start)
    apply_source = source[start:end]

    assert "selectedCategory() === EXTERNAL_CATEGORY" in apply_source
    assert "standard.hidden = external" in apply_source
    assert "standard.style.display = external ? 'none' : ''" in apply_source
    assert "evaluation.hidden = !external" in apply_source
    assert "evaluation.style.display = external ? '' : 'none'" in apply_source
    assert "evaluationBody.hidden = !external" in apply_source
    assert ".click()" not in apply_source


def test_summary_is_visibility_only_not_lifecycle_owner() -> None:
    source = _source(SUMMARY)

    assert "API Key Lifecycle Summary" in source
    assert "ensureEvaluationCard" not in source
    assert "external_evaluation" not in source
    assert "MutationObserver" not in source
    assert "method: 'POST'" not in source
    assert "method: 'DELETE'" not in source


def test_session_verifies_but_does_not_construct_or_move_lifecycle() -> None:
    source = _source(SESSION)

    assert "fetch('/auth/me'" in source
    assert "window.PMK_ADMIN_SESSION" in source
    assert "pmk-admin-session-verified" in source
    assert "const VERIFICATION_HOST_ID = 'admin-evaluation-verification-controls'" in source
    assert "ensureEvaluationGrantPlaceholder" not in source
    assert "admin-api-key-lifecycle-card" not in source
    assert "insertBefore" not in source
    assert "appendChild(host)" not in source


def test_provisioning_has_no_independent_external_evaluation_mode() -> None:
    source = _source(PROVISIONING)

    assert "admin-api-key-provisioning-mode" not in source
    assert "Standard / Integration Key" not in source
    assert "admin-api-key-external-provisioning-slot" in source


def test_grant_creation_is_hard_blocked_until_every_gate_is_ready() -> None:
    source = _source(EVALUATION)

    required = [
        "category === EXTERNAL_CATEGORY",
        "document.body.dataset.adminSession === 'ok'",
        "grantAuthority === 'authorized' || grantAuthority === 'loaded'",
        "Boolean(profile)",
        "endpoints.length > 0",
        "scopes.length > 0",
        "tasks.length > 0",
        "purpose.length >= 10",
        "duration >= 1 && duration <= 90",
        "quota >= 1 && quota <= 10000",
        "button.disabled = !readiness.ready",
        "if (!readiness.ready)",
    ]
    for marker in required:
        assert marker in source


def test_grant_post_uses_only_evaluation_grant_authority() -> None:
    source = _source(EVALUATION)

    create_start = source.index("async function createEvaluationGrant()")
    issue_start = source.index("async function issueEvaluationKey", create_start)
    create_source = source[create_start:issue_start]

    assert "EVALUATION_GRANTS_ENDPOINT, 'POST'" in create_source
    assert "client_id: readiness.clientId" in create_source
    assert "issued_to: readiness.issuedTo" in create_source
    assert "allowed_task_ids: readiness.tasks" in create_source
    assert "expires_in_days: readiness.duration" in create_source
    assert "max_requests: readiness.quota" in create_source
    assert "/settings/api-keys" not in create_source


def test_operational_profile_remains_intent_only_not_scope_authority() -> None:
    provisioning = _source(PROVISIONING)

    assert "Choosing a profile does not mutate runtime scopes" in provisioning
    assert "selectedEndpointScopes" in provisioning
    assert "derivedScopes.join('\\n')" in provisioning
    assert "profile.allowed_scopes" in provisioning
    assert "target.value = profile" not in provisioning
