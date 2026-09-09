from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
LIFECYCLE = JS / "admin_api_key_evaluation_lifecycle.js"
EVALUATION = JS / "admin_evaluation_grants.js"
SESSION = JS / "admin_session.js"
RUNTIME_FIXUPS = JS / "admin_runtime_fixups.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_external_evaluation_card_is_embedded_in_admin_api_key_lifecycle_without_legacy_button() -> None:
    source = _source(SESSION)

    required = [
        "const API_KEY_LIFECYCLE_CARD_ID = 'admin-api-key-lifecycle-card'",
        "const EVALUATION_CARD_ID = 'admin-api-key-external-evaluation-card'",
        "const EVALUATION_BODY_ID = 'admin-api-key-external-evaluation-body'",
        "const lifecycleCard = document.getElementById(API_KEY_LIFECYCLE_CARD_ID)",
        "if (!lifecycleCard) return null",
        "const lifecycleForm = lifecycleCard.querySelector('.admin-grid')",
        "lifecycleCard.insertBefore(card, lifecycleForm)",
        "External Evaluation Authority",
        "PostgreSQL-backed Evaluation authority is authoritative",
    ]
    for marker in required:
        assert marker in source

    assert "EVALUATION_ACTIVATE_ID" not in source
    assert "Activate External Evaluation" not in source
    assert "External Evaluation Active" not in source
    assert "page.appendChild(host)" not in source
    assert "fallback-page" not in source


def test_category_selection_directly_controls_evaluation_visibility_and_verification() -> None:
    source = _source(SESSION)

    required = [
        "function externalEvaluationSelected()",
        "document.getElementById('admin-api-key-category')?.value === EXTERNAL_CATEGORY",
        "function syncEvaluationSelectionState()",
        "card.hidden = !selected",
        "body.hidden = !selected",
        "card.dataset.activated = selected ? 'true' : 'false'",
        "window.addEventListener('pmk-api-key-category-changed'",
        "await checkAdminSession();",
    ]
    for marker in required:
        assert marker in source

    assert ".click()" not in source
    assert "applyExternalEvaluationActivation" not in source


def test_external_evaluation_moves_provisioning_workspace_inside_selected_lifecycle() -> None:
    source = _source(SESSION)

    required = [
        "const PROVISIONING_WORKSPACE_ID = 'admin-api-key-provisioning-workspace'",
        "function placeEvaluationWorkspaceInsideCard()",
        "if (!externalEvaluationSelected()) return",
        "const body = document.getElementById(EVALUATION_BODY_ID)",
        "const host = document.getElementById(EVALUATION_HOST_ID)",
        "const workspace = document.getElementById(PROVISIONING_WORKSPACE_ID)",
        "if (!body || !workspace) return",
        "if (workspace.parentElement !== body) body.insertBefore(workspace, host || body.firstChild)",
    ]
    for marker in required:
        assert marker in source


def test_admin_session_requires_identity_and_platform_admin_authority() -> None:
    source = _source(SESSION)

    required = [
        "const AUTHORITY_ENDPOINT = '/settings/admin/evaluation-grants/authority'",
        "const token = window.PMK_ADMIN_AUTH?.bearer?.() || ''",
        "Active administrator Identity session required",
        "authority?.authorized !== true",
        "authority?.authority !== 'platform_admin'",
        "Authenticated identity does not hold active Platform Administrator authority.",
    ]
    for marker in required:
        assert marker in source

    assert "isAdminSession" not in source
    assert "canManageEvaluationGrants" not in source


def test_evaluation_lifecycle_keeps_grant_host_inside_external_evaluation_card() -> None:
    source = _source(LIFECYCLE)

    required = [
        "admin-api-key-provisioning-workspace",
        "admin-api-key-external-evaluation-card",
        "admin-api-key-external-evaluation-body",
        "admin-api-key-evaluation-lifecycle-slot",
        "admin-evaluation-grants",
        "externalBody.appendChild(slot)",
        "hostSlot.appendChild(host)",
        "host.dataset.lifecycleEmbedded = 'true'",
        "Evaluation Access & Key Handoff",
    ]
    for marker in required:
        assert marker in source

    assert "workspace.appendChild(slot)" not in source
    assert "/settings/admin/evaluation-grants" in source


def test_external_evaluation_mode_hides_standard_key_form_and_shows_evaluation_surfaces() -> None:
    source = _source(LIFECYCLE)

    assert "mode() === 'external_evaluation'" in source
    assert "standardGrid.hidden = evaluationMode" in source
    assert "scopesLabel.hidden = evaluationMode" in source
    assert "actions.hidden = evaluationMode" in source
    assert "slot.hidden = !evaluationMode" in source
    assert "externalBody.hidden = false" in source
    assert "delivery/receipt evidence" in source
    assert "backend-authoritative" in source


def test_runtime_fixups_cannot_reintroduce_standard_key_generation_in_external_evaluation() -> None:
    source = _source(RUNTIME_FIXUPS)

    required = [
        "const EXTERNAL_CATEGORY = 'external_evaluation'",
        "function externalEvaluationSelected()",
        "removeApiKeyProfileControls();",
        "if (externalEvaluationSelected())",
        "Standard API key generation is blocked for External Evaluation.",
        "button.disabled = true",
        "window.addEventListener('pmk-api-key-category-changed'",
    ]
    for marker in required:
        assert marker in source

    generation_start = source.index("async function generateProfiledApiKey()")
    request_start = source.index("const profileName", generation_start)
    guard_source = source[generation_start:request_start]
    assert "if (externalEvaluationSelected())" in guard_source
    assert "return;" in guard_source
    assert "request('POST', '/settings/api-keys'" not in guard_source


def test_evaluation_lifecycle_preview_uses_real_grant_inputs_and_tasks() -> None:
    source = _source(LIFECYCLE)

    required = [
        "admin-eval-client-id",
        "admin-eval-issued-to",
        "admin-eval-days",
        "admin-eval-max-requests",
        "admin-eval-purpose",
        "[data-eval-task]:checked",
        "Evaluation Access Preview",
        "Bound canonical tasks",
        "subscription",
        "production",
    ]
    for marker in required:
        assert marker in source


def test_evaluation_lifecycle_attachment_is_bounded_and_observes_grant_refreshes() -> None:
    source = _source(LIFECYCLE)

    assert "const MAX_ATTACH_ATTEMPTS = 30" in source
    assert "const ATTACH_RETRY_MS = 100" in source
    assert "attachAttempts < MAX_ATTACH_ATTEMPTS" in source
    assert "window.setTimeout" in source
    assert "new MutationObserver" in source
    assert "grantObserver.observe(host, { childList: true, subtree: true })" in source
    assert "while (" not in source


def test_evaluation_key_delivery_receipt_and_revoke_controls_are_explicit() -> None:
    source = _source(LIFECYCLE)

    required = [
        "Confirm Key Sent",
        "Confirm Receipt",
        "Revoke API Key",
        "confirm-delivery",
        "acknowledge",
        "data-eval-key-revoke",
        "administrator_revoked_from_external_evaluation_ui",
        "The key will be rejected immediately by the runtime.",
        "raw secret visible: no",
        "production: disabled",
    ]
    for marker in required:
        assert marker in source


def test_evaluation_key_lifecycle_never_persists_or_rehydrates_raw_secret() -> None:
    source = _source(LIFECYCLE)

    assert "localStorage.setItem" not in source
    assert "sessionStorage.setItem" not in source
    assert "result.api_key" not in source
    assert "payload.api_key" not in source
    assert "raw secret visible: no" in source


def test_session_loads_evaluation_controls_only_after_verified_platform_admin_authority() -> None:
    source = _source(SESSION)

    required = [
        "API_KEY_EVALUATION_LIFECYCLE_SCRIPT_SELECTOR",
        "admin_api_key_evaluation_lifecycle.js?v=adminapikevaluation-authority-v2",
        "admin_api_key_provisioning_workspace.js?v=adminapikeyworkspace-authority-v2",
        "admin_evaluation_grants.js?v=admineval-authority-v2",
        "function loadProtectedEvaluationControls()",
        "document.body.dataset.adminSession = 'ok'",
        "document.body.dataset.adminEvaluationGrants = 'authorized'",
        "const AUTHORITY_ENDPOINT = '/settings/admin/evaluation-grants/authority'",
        "authority?.authorized !== true",
        "authority?.authority !== 'platform_admin'",
    ]
    for marker in required:
        assert marker in source

    assert source.index("document.body.dataset.adminSession = 'ok'") < source.index(
        "loadProtectedEvaluationControls();"
    )
    assert "canManageEvaluationGrants" not in source
    assert "EVALUATION_ADMIN_ROLES" not in source


def test_session_refresh_preserves_mfa_and_csrf_fail_closed_boundary() -> None:
    source = _source(SESSION)

    for marker in (
        "const SESSION_REFRESH_ENDPOINT = '/auth/session/refresh'",
        "const CSRF_COOKIE = 'pmk_csrf_token'",
        "if (refreshInFlight) return refreshInFlight",
        "'X-CSRF-Token': csrf",
        "if (payload?.mfa_required === true) return false",
        "sessionStorage.setItem('maestro_token', token)",
        "markSessionExpired(response.status)",
    ):
        assert marker in source


def test_evaluation_key_issue_result_is_complete_and_copyable_once() -> None:
    source = _source(EVALUATION)

    required = [
        "One-time evaluation API key created.",
        "admin-eval-copy-issued-key",
        "navigator.clipboard.writeText(secret)",
        "key.scopes",
        "key.task_scope_ids",
        "key.allowed_task_ids",
        "key.allowed_binding_ids",
        "key.evaluation_request_limit",
        "key.expires_at",
        "usage.example_endpoint",
        "Subscription required",
        "Production",
    ]
    for marker in required:
        assert marker in source

    assert "key.quota_limit" not in source
    assert "sessionStorage.setItem" not in source
    assert "localStorage.setItem" not in source


def test_evaluation_module_emits_selection_events_for_live_preview() -> None:
    source = _source(EVALUATION)

    assert "pmk-evaluation-selection-changed" in source
    assert "dispatchEvaluationSelectionChanged" in source
    assert "host.addEventListener('input', dispatchEvaluationSelectionChanged)" in source
    assert "host.addEventListener('change', dispatchEvaluationSelectionChanged)" in source


def test_evaluation_grant_cards_show_scopes_tasks_request_limit_and_expiry() -> None:
    source = _source(EVALUATION)

    assert "grant.allowed_scopes" in source
    assert "grant.allowed_task_ids" in source
    assert "grant.allowed_binding_ids" in source
    assert "grant.max_requests" in source
    assert "request limit" in source
    assert "grant.expires_at" in source
    assert "subscription required: no" in source
    assert "production: disabled" in source
