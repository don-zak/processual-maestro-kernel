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


def test_evaluation_management_loader_is_idempotent_and_reports_asset_failure() -> None:
    source = _session_source()

    assert "document.querySelector(EVALUATION_SCRIPT_SELECTOR)" in source
    assert "if (document.querySelector(EVALUATION_SCRIPT_SELECTOR)) return;" in source
    assert "script.addEventListener('error'" in source
    assert "admin-evaluation-grants-load-error" in source
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
