from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
LIFECYCLE = JS / "admin_api_key_evaluation_lifecycle.js"
EVALUATION = JS / "admin_evaluation_grants.js"
SESSION = JS / "admin_session.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_evaluation_lifecycle_embeds_existing_grant_host_in_workspace() -> None:
    source = _source(LIFECYCLE)

    required = [
        "admin-api-key-provisioning-workspace",
        "admin-api-key-evaluation-lifecycle-slot",
        "admin-evaluation-grants",
        "hostSlot.appendChild(host)",
        "host.dataset.lifecycleEmbedded = 'true'",
        "External Evaluation Lifecycle",
    ]
    for marker in required:
        assert marker in source

    assert "document.createElement('div')" not in source
    assert "/settings/admin/evaluation-grants" not in source


def test_external_evaluation_mode_hides_standard_key_form_and_actions() -> None:
    source = _source(LIFECYCLE)

    assert "mode() === 'external_evaluation'" in source
    assert "standardGrid.hidden = evaluationMode" in source
    assert "scopesLabel.hidden = evaluationMode" in source
    assert "actions.hidden = evaluationMode" in source
    assert "slot.hidden = !evaluationMode" in source
    assert "evaluation grant authority" in source


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


def test_evaluation_lifecycle_attachment_is_bounded_without_dom_observer() -> None:
    source = _source(LIFECYCLE)

    assert "const MAX_ATTACH_ATTEMPTS = 30" in source
    assert "const ATTACH_RETRY_MS = 100" in source
    assert "attachAttempts < MAX_ATTACH_ATTEMPTS" in source
    assert "window.setTimeout" in source
    assert "MutationObserver" not in source
    assert "while (" not in source


def test_session_loads_evaluation_lifecycle_only_after_verified_admin_authority() -> None:
    source = _source(SESSION)

    required = [
        "API_KEY_EVALUATION_LIFECYCLE_SCRIPT_SELECTOR",
        "admin_api_key_evaluation_lifecycle.js?v=adminapikevaluation01",
        "function loadApiKeyEvaluationLifecycle()",
        "script.dataset.adminApiKeyEvaluationLifecycle = 'true'",
        "document.body.dataset.adminSession = 'ok'",
        "if (canManageEvaluationGrants(me))",
        "loadEvaluationGrantControls();",
        "loadApiKeyEvaluationLifecycle();",
    ]
    for marker in required:
        assert marker in source

    assert source.index("document.body.dataset.adminSession = 'ok'") < source.index(
        "loadApiKeyEvaluationLifecycle();"
    )
    assert source.index("if (canManageEvaluationGrants(me))") < source.index(
        "loadApiKeyEvaluationLifecycle();"
    )


def test_evaluation_key_issue_result_is_complete_and_copyable_once() -> None:
    source = _source(EVALUATION)

    required = [
        "One-time evaluation API key created.",
        "admin-eval-copy-issued-key",
        "navigator.clipboard.writeText(secret)",
        "key.scopes",
        "key.task_scope_ids",
        "key.allowed_task_ids",
        "key.quota_limit",
        "key.expires_at",
        "usage.example_endpoint",
        "Subscription required",
        "Production",
    ]
    for marker in required:
        assert marker in source

    assert "sessionStorage.setItem" not in source
    assert "localStorage.setItem" not in source


def test_evaluation_module_emits_selection_events_for_live_preview() -> None:
    source = _source(EVALUATION)

    assert "pmk-evaluation-selection-changed" in source
    assert "dispatchEvaluationSelectionChanged" in source
    assert "host.addEventListener('input', dispatchEvaluationSelectionChanged)" in source
    assert "host.addEventListener('change', dispatchEvaluationSelectionChanged)" in source


def test_evaluation_grant_cards_show_scopes_tasks_quota_and_expiry() -> None:
    source = _source(EVALUATION)

    assert "grant.allowed_scopes" in source
    assert "grant.allowed_task_ids" in source
    assert "grant.max_requests" in source
    assert "grant.expires_at" in source
    assert "subscription required: no" in source
    assert "production: disabled" in source
