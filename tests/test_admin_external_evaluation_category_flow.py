from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
SUMMARY = JS / "admin_api_key_summary.js"
EVALUATION = JS / "admin_evaluation_grants.js"
SESSION = JS / "admin_session.js"
PROVISIONING = JS / "admin_api_key_provisioning_workspace.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_external_evaluation_is_a_real_category_driven_lifecycle_choice() -> None:
    source = _source(SUMMARY)

    required = [
        "const EXTERNAL_CATEGORY = 'external_evaluation'",
        "option.value = EXTERNAL_CATEGORY",
        "External Evaluation Access - governed sandbox evaluation",
        "API Key Category",
        "single lifecycle authority",
        "select.addEventListener('change', applyCategoryState)",
        "card.dataset.activated = external ? 'true' : 'false'",
        "setMode('external_evaluation')",
        "setMode('standard')",
    ]
    for marker in required:
        assert marker in source


def test_external_evaluation_does_not_require_a_visible_activate_button() -> None:
    source = _source(SUMMARY)

    assert "if (button) button.hidden = true" in source
    assert "This lifecycle is selected from Category." in source
    assert "External Evaluation Lifecycle" in source
    assert "verify → provision → bind tasks → create grant → issue once → test → revoke" in source


def test_external_evaluation_category_switches_away_from_standard_surfaces() -> None:
    source = _source(SUMMARY)

    assert "setStandardVisibility(!external)" in source
    assert "node.hidden = visible" in source
    assert "admin-api-key-category-authority" in source
    assert "slot.appendChild(label)" in source


def test_external_evaluation_renders_the_plan_contract_before_creation() -> None:
    source = _source(SUMMARY)

    required = [
        "External Evaluation Readiness Contract",
        "Category",
        "Administrator",
        "Provisioning",
        "Operational profile",
        "Eligible endpoints",
        "Derived scopes",
        "Canonical tasks",
        "Identity",
        "Purpose",
        "Plan contract incomplete",
        "Create Evaluation Grant must remain disabled",
    ]
    for marker in required:
        assert marker in source


def test_grant_creation_is_hard_blocked_until_every_plan_gate_is_ready() -> None:
    source = _source(EVALUATION)

    required = [
        "function evaluationReadiness()",
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
        "Evaluation grant creation blocked by the lifecycle readiness contract.",
    ]
    for marker in required:
        assert marker in source


def test_grant_post_uses_only_readiness_contract_values() -> None:
    source = _source(EVALUATION)

    create_start = source.index("async function createEvaluationGrant()")
    issue_start = source.index("async function issueEvaluationKey", create_start)
    create_source = source[create_start:issue_start]

    assert "const readiness = updateEvaluationReadiness();" in create_source
    assert "if (!readiness.ready)" in create_source
    assert "EVALUATION_GRANTS_ENDPOINT, 'POST'" in create_source
    assert "client_id: readiness.clientId" in create_source
    assert "issued_to: readiness.issuedTo" in create_source
    assert "allowed_task_ids: readiness.tasks" in create_source
    assert "allowed_scopes: readiness.scopes" in create_source
    assert "expires_in_days: readiness.duration" in create_source
    assert "max_requests: readiness.quota" in create_source
    assert "/settings/api-keys" not in create_source


def test_evaluation_issue_remains_one_time_and_never_persists_raw_secret() -> None:
    source = _source(EVALUATION)

    required = [
        "One-time evaluation API key created.",
        "Copy it now; it will not be displayed again.",
        "X-API-Key:",
        "Copy API Key",
        "Bound tasks:",
        "Subscription required",
        "Production",
    ]
    for marker in required:
        assert marker in source

    assert "sessionStorage.setItem" not in source
    assert "localStorage.setItem" not in source


def test_evaluation_grant_host_has_no_page_level_fallback() -> None:
    source = _source(EVALUATION)

    assert "admin-api-key-external-evaluation-body" in source
    assert "page.appendChild(host)" not in source
    assert "const page = document.getElementById('page-admin-api-keys')" not in source


def test_existing_backend_authorities_and_scope_derivation_are_preserved() -> None:
    evaluation = _source(EVALUATION)
    provisioning = _source(PROVISIONING)
    session = _source(SESSION)

    assert "/settings/admin/evaluation-grants" in evaluation
    assert "selectedScopes" in provisioning
    assert "selectedEndpoints" in provisioning
    assert "pmk-api-key-access-selection-changed" in provisioning
    assert "loadEvaluationGrantControls();" in session
    assert "loadApiKeyProvisioningWorkspace();" in session


def test_operational_profile_remains_intent_only_not_scope_authority() -> None:
    provisioning = _source(PROVISIONING)

    assert "Selected operational intent only" in provisioning
    assert "selectedEndpointScopes" in provisioning
    assert "target.value = derivedScopes.join('\\n')" in provisioning
    assert "profile.allowed_scopes" in provisioning
    assert "target.value = profile" not in provisioning
