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


def test_task_execute_returns_quota_and_status_without_making_them_authority() -> None:
    runtime = source(RUNTIME)

    assert "_decorate_execution_with_status" in runtime
    assert 'response["quota"] = snapshot["quota"]' in runtime
    assert 'response["execution_status"] = snapshot.get("latest_execution")' in runtime
    assert "except HTTPException:" in runtime
    assert "claim_evaluation_execution" in runtime


def test_customer_portal_uses_memory_only_api_key_and_customer_runtime_endpoints() -> None:
    html = source(PORTAL)
    js = source(PORTAL_JS)

    assert "Maestro External Evaluation" in html
    assert "evaluation_client_portal.js" in html
    assert "Executions used" in html
    assert "Remaining" in html
    assert "Latest execution" in html
    assert "Evidence" in html
    assert "/evaluation/runtime/status" in js
    assert "/evaluation/runtime/task-execute" in js
    assert "X-API-Key" in js
    assert "credentials: 'omit'" in js
    assert "window.setInterval" in js
    assert "5000" in js
    assert "localStorage" not in js
    assert "sessionStorage" not in js


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
