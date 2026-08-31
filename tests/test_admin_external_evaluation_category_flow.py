from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
SUMMARY = JS / "admin_api_key_summary.js"
EVALUATION = JS / "admin_evaluation_grants.js"
SESSION = JS / "admin_session.js"
PROVISIONING = JS / "admin_api_key_provisioning_workspace.js"
RUNTIME_FIXUPS = JS / "admin_runtime_fixups.js"


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


def test_external_evaluation_has_no_visible_legacy_activation_path() -> None:
    session = _source(SESSION)

    assert "This lifecycle is selected only from API Key Category." in session
    assert "External Evaluation Lifecycle" in session
    assert "verify → provision → bind tasks → create grant → issue once → test → revoke" in session
    assert "Activate External Evaluation" not in session
    assert "External Evaluation Active" not in session
    assert "EVALUATION_ACTIVATE_ID" not in session
    assert "applyExternalEvaluationActivation" not in session
    assert ".click()" not in session


def test_external_evaluation_category_switches_away_from_standard_surfaces() -> None:
    summary = _source(SUMMARY)
    runtime = _source(RUNTIME_FIXUPS)

    assert "setStandardVisibility(!external)" in summary
    assert "node.hidden = visible" in summary
    assert "admin-api-key-category-authority" in summary
    assert "slot.appendChild(label)" in summary
    assert "removeApiKeyProfileControls();" in runtime
    assert "data.standardApiKeyOnly" not in runtime
    assert "controls.dataset.standardApiKeyOnly = 'true'" in runtime


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
        "!runtimeSelected || bindings.length > 0",
        "!runtimeSelected || bindingsPrepared",
        "purpose.length >= 10",
        "duration >= 1 && duration <= 90",
        "requestLimit >= 1 && requestLimit <= 5000",
        "button.disabled = !readiness.ready",
        "if (!readiness.ready)",
        "Evaluation grant creation blocked by the lifecycle readiness contract.",
    ]
    for marker in required:
        assert marker in source


def test_grant_post_uses_complete_readiness_contract_values() -> None:
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
    assert "allowed_binding_ids: readiness.bindings" in create_source
    assert "allowed_endpoints: readiness.endpoints" in create_source
    assert "const allowedScopes = readiness.scopes;" in create_source
    assert "...(allowedScopes.length ? { allowed_scopes: allowedScopes } : {})" in create_source
    assert "expires_in_days: readiness.duration" in create_source
    assert "max_requests: readiness.requestLimit" in create_source
    assert "selectedEvaluationScopes();" not in create_source
    assert "/settings/api-keys" not in create_source


def test_runtime_task_execution_requires_prepared_evaluation_binding() -> None:
    source = _source(EVALUATION)

    required = [
        "EVALUATION_BINDING_CATALOG_ENDPOINT",
        "'/settings/admin/evaluation-grants/binding-catalog'",
        "RUNTIME_TASK_ENDPOINT = '/evaluation/runtime/task-execute'",
        "Prepared Evaluation Bindings",
        "function runtimeTaskEndpointSelected",
        "function selectedEvaluationBindings",
        "function renderEvaluationBindingCatalog",
        "item.selectable === true && taskAllowed",
        "Runtime task execution requires at least one prepared Evaluation binding.",
        "Every selected binding must be sandbox-ready and match a selected canonical task.",
    ]
    for marker in required:
        assert marker in source


def test_evaluation_request_limit_matches_backend_contract() -> None:
    source = _source(EVALUATION)

    assert 'id="admin-eval-max-requests" type="number" min="1" max="5000"' in source
    assert "requestLimit >= 1 && requestLimit <= 5000" in source
    assert "Evaluation request limit must be between 1 and 5000." in source
    assert "key.evaluation_request_limit" in source
    assert "key.quota_limit" not in source
    assert "quota-bound" not in source
    assert "<strong>Quota</strong>" not in source


def test_standard_runtime_fixup_cannot_generate_an_external_evaluation_key() -> None:
    source = _source(RUNTIME_FIXUPS)

    generation_start = source.index("async function generateProfiledApiKey()")
    profile_start = source.index("const profileName", generation_start)
    guard = source[generation_start:profile_start]

    assert "if (externalEvaluationSelected())" in guard
    assert "Standard API key generation is blocked for External Evaluation." in guard
    assert "button.disabled = true" in guard
    assert "return;" in guard
    assert "request('POST', '/settings/api-keys'" not in guard


def test_evaluation_issue_remains_one_time_and_never_persists_raw_secret() -> None:
    source = _source(EVALUATION)

    required = [
        "One-time evaluation API key created.",
        "Copy it now; it will not be displayed again.",
        "X-API-Key:",
        "Copy API Key",
        "Bound tasks:",
        "Prepared bindings:",
        "Evaluation request limit",
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
    assert "loadApiKeyEvaluationLifecycle();" in session


def test_operational_profile_remains_intent_only_not_scope_authority() -> None:
    provisioning = _source(PROVISIONING)

    assert "Selected operational intent only" in provisioning
    assert "selectedEndpointScopes" in provisioning
    assert "target.value = derivedScopes.join('\\n')" in provisioning
    assert "profile.allowed_scopes" in provisioning
    assert "target.value = profile" not in provisioning
