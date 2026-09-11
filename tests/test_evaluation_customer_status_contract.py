from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "processual_api" / "routers" / "evaluation_runtime.py"
AUTHORITY = ROOT / "processual_api" / "services" / "evaluation_authority_postgres.py"
PORTAL = ROOT / "processual_api" / "static" / "evaluation.html"
PORTAL_JS = ROOT / "processual_api" / "static" / "js" / "evaluation_client_portal.js"
ADMIN_JS = ROOT / "processual_api" / "static" / "js" / "admin_api_key_evaluation_lifecycle.js"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_customer_status_endpoint_is_zero_quota_and_safe() -> None:
    runtime = source(RUNTIME)
    authority = source(AUTHORITY)

    assert '@router.get("/status"' in runtime
    assert "evaluation_key_runtime_status" in runtime
    assert '"status_endpoint_consumes_quota": False' in runtime
    assert "key.usage_count += 1" not in authority.split(
        "async def evaluation_key_runtime_status", 1
    )[1].split("async def update_evaluation_authority_key_lifecycle", 1)[0]
    assert '"raw_secret_visible": False' in authority
    assert '"production_allowed": False' in authority


def test_customer_execution_status_is_scoped_and_zero_quota() -> None:
    runtime = source(RUNTIME)

    assert '@router.get("/executions/{execution_id}"' in runtime
    assert "get_evaluation_execution_status" in runtime
    assert '"status_endpoint_consumes_quota": False' in runtime
    assert '"raw_secret_visible": False' in runtime
    assert '"production_allowed": False' in runtime


def test_task_execute_returns_quota_and_exact_execution_status() -> None:
    runtime = source(RUNTIME)
    decorator = runtime.split("async def _decorate_execution_with_status", 1)[1].split(
        '@router.get("/status"', 1
    )[0]
    task_execute = runtime.split('@router.post("/task-execute"', 1)[1]

    assert "get_evaluation_execution_status" in decorator
    assert 'response["quota"] = credential["quota"]' in decorator
    assert 'response["execution_status"] = receipt' in decorator
    assert 'snapshot.get("latest_execution")' not in decorator
    assert 'record_id = str(claim["record"]["record_id"])' in task_execute
    assert task_execute.count("execution_id=record_id") >= 2
    assert "claim_evaluation_execution" in task_execute


def test_customer_portal_uses_memory_only_api_key_and_runtime_endpoints() -> None:
    html = source(PORTAL)
    js = source(PORTAL_JS)

    assert "Processual Maestro — External Evaluation" in html
    assert "External Evaluation Workspace" in html
    assert "evaluation_client_portal.js?v=eval-client-authority-v4" in html
    assert "evaluation_client_portal.js?v=eval-client-authority-v3" not in html
    for marker in (
        'id="quota-used"',
        'id="quota-remaining"',
        "Authoritative Evaluation quota",
        "Guided proof-of-value scenarios",
        'id="scenario-select"',
        'id="prepare-scenario"',
        'id="execution-state"',
        'id="evidence-state"',
        'id="quota-effect"',
        "New admitted execution: +1 · durable replay: +0",
    ):
        assert marker in html
    assert "/evaluation/runtime/status" in js
    assert "/evaluation/runtime/task-execute" in js
    assert "X-API-Key" in js
    assert "credentials: 'omit'" in js
    assert "window.setInterval" in js
    assert "5000" in js
    assert "localStorage" not in js
    assert "sessionStorage" not in js


def test_customer_portal_execute_button_tracks_runtime_authority_quota_and_binding() -> None:
    js = source(PORTAL_JS)

    assert "let runtimeState" in js
    assert "runtimeState.credentialStatus === 'active'" in js
    assert "Number(runtimeState.quotaRemaining) > 0" in js
    assert "!runtimeState.executing" in js
    assert "$('task-id').value.trim()" in js
    assert "$('binding-id').value.trim()" in js
    assert "syncExecuteButton" in js
    assert "runtimeState.credentialStatus = 'unavailable'" in js
    assert "runtimeState.quotaRemaining = 0" in js
    assert "button.disabled = !apiKey" not in js


def test_customer_portal_scenarios_never_add_grant_authority() -> None:
    js = source(PORTAL_JS)

    assert "CRM-CONTEXT-01" in js
    assert "CRM-SUMMARY-01" in js
    assert "CRM-DRAFT-01" in js
    assert "scenarioCandidates()" in js
    assert "runtimeState.allowedTasks" in js
    assert "runtimeState.allowedBindings" in js
    assert "Selected scenario is outside the grant task authority." in js
    assert "No authority was added; server-side grant checks remain authoritative." in js
    assert "allowedEndpoints.push" not in js
    assert "allowedTasks.push" not in js
    assert "allowedBindings.push" not in js


def test_customer_portal_reports_quota_effect_after_failed_execution() -> None:
    js = source(PORTAL_JS)

    assert "Execution failed after admission; the admitted-execution unit remains consumed." in js
    assert "Request failed before admission; no evaluation quota unit was consumed." in js
    assert "const afterUsed = Number(statusPayload?.quota?.used ?? beforeUsed)" in js


def test_admin_external_evaluation_shows_safe_audit_receipts_and_portal_location() -> None:
    js = source(ADMIN_JS)

    assert "Evaluation Access & Key Handoff" in js
    assert "/console/evaluation.html" in js
    assert "Execution Audit" in js
    assert "Final Evaluation Summary" in js
    assert "audit-receipts?limit=100" in js
    assert "audit outcome" in js
    assert "operator required" in js
    assert "raw secret: no" in js
    assert "raw task input: no" in js
    assert "admitted executions used" in js
