from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_EVALUATION_UI = (
    ROOT / "processual_api" / "static" / "js" / "admin_evaluation_grants.js"
)
CUSTOMER_PORTAL = ROOT / "processual_api" / "static" / "evaluation.html"
CUSTOMER_PORTAL_JS = (
    ROOT / "processual_api" / "static" / "js" / "evaluation_client_portal.js"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_customer_handoff_contains_operational_context_needed_for_evaluation() -> None:
    source = _read(ADMIN_EVALUATION_UI)

    required = (
        "Processual Maestro — External Evaluation Access",
        "Portal:",
        "Authentication header: X-API-Key",
        "Evaluation Grant ID:",
        "API Key ID:",
        "API Key prefix:",
        "Evaluation type:",
        "Admitted-execution quota:",
        "Expires:",
        "Allowed canonical tasks:",
        "Prepared bindings:",
        "Allowed endpoints:",
        "Idempotency:",
        "durable replay consumes +0 quota",
        "Execution stages: admitted -> executing -> succeeded/failed -> evidence persisted.",
        "Status/dashboard reads consume +0 quota.",
        "Subscription/registration/commercial quota: not required.",
        "Production execution: disabled.",
        "Use only synthetic/non-production data",
        "final qualification remains operator-controlled",
    )
    for marker in required:
        assert marker in source


def test_one_time_secret_and_safe_handoff_are_separate_copy_boundaries() -> None:
    source = _read(ADMIN_EVALUATION_UI)
    handoff = source.split("function handoffText", 1)[1].split(
        "async function issueEvaluationKey", 1
    )[0]
    issue = source.split("async function issueEvaluationKey", 1)[1].split(
        "async function revokeEvaluationGrant", 1
    )[0]

    assert "raw_key" not in handoff
    assert "api_key" not in handoff
    assert "hashed" not in handoff
    assert "key_hash" not in handoff
    assert "provider_secret" not in handoff
    assert "navigator.clipboard.writeText(secret)" in issue
    assert "navigator.clipboard.writeText(safeHandoff)" in issue
    assert "approved secret-delivery channel separately from the safe handoff text" in issue


def test_handoff_type_and_quota_are_grant_derived_not_commercial_overrides() -> None:
    source = _read(ADMIN_EVALUATION_UI)
    handoff = source.split("function handoffText", 1)[1].split(
        "async function issueEvaluationKey", 1
    )[0]

    assert "grant?.evaluation_type" in handoff
    assert "grant?.max_requests" in handoff
    assert "evaluation_request_limit" in handoff
    assert "plan_id" not in handoff
    assert "quota_limit_override" not in handoff


def test_customer_portal_matches_the_handoff_execution_story() -> None:
    html = _read(CUSTOMER_PORTAL)
    js = _read(CUSTOMER_PORTAL_JS)

    for marker in (
        "External Evaluation Workspace",
        "Production execution: disabled",
        "Quota used",
        "Quota remaining",
        "Latest execution",
        "Safe evidence",
    ):
        assert marker in html

    for marker in (
        "/evaluation/runtime/status",
        "/evaluation/runtime/task-execute",
        "X-API-Key",
        "external_evaluation_customer_receipt",
        "qualification_decision",
        "operator_required",
    ):
        assert marker in js

    assert "localStorage" not in js
    assert "sessionStorage" not in js
