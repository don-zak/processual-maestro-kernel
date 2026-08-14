from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "processual_api" / "static" / "js" / "admin_api_key_summary.js"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_admin_api_key_area_exposes_evaluation_grant_controls() -> None:
    source = _source()

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
    source = _source()

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
    source = _source()

    assert "window.PMK_ADMIN_AUTH" in source
    assert "credentials: 'include'" in source
    assert "X-API-Key:" in source
    assert "Copy it now; it will not be displayed again." in source
    assert "key_hash" not in source
    assert "provider_secret" not in source


def test_evaluation_grant_ui_requires_at_least_one_task() -> None:
    source = _source()

    assert "Select at least one canonical task for the API key content." in source
    assert "if (!allowedTaskIds.length)" in source


def test_api_key_summary_script_is_invoked() -> None:
    source = _source().rstrip()
    assert source.endswith("})();")
