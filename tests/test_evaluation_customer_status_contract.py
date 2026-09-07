from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "processual_api" / "routers" / "evaluation_runtime.py"
AUTHORITY = ROOT / "processual_api" / "services" / "evaluation_authority_postgres.py"
DELIVERY = ROOT / "processual_api" / "services" / "evaluation_runtime_delivery_postgres.py"
REGISTRY = ROOT / "processual_api" / "routers" / "external_evaluation_route_registry.py"
PORTAL = ROOT / "processual_api" / "static" / "evaluation.html"
PORTAL_JS = ROOT / "processual_api" / "static" / "js" / "evaluation_client_portal.js"
ADMIN_JS = ROOT / "processual_api" / "static" / "js" / "admin_api_key_evaluation_lifecycle.js"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_customer_status_endpoint_is_free_and_key_scoped() -> None:
    runtime = source(RUNTIME)
    authority = source(AUTHORITY)

    assert '@router.get("/status", response_model=dict)' in runtime
    assert 'Depends(require_scope("run:evaluation"))' in runtime
    assert "evaluation_key_runtime_status(owner_id, grant_id, api_key_id)" in runtime
    assert '"status_endpoint_consumes_quota": False' in runtime
    assert "async def evaluation_key_runtime_status(" in authority
    assert '"status_checks_consume_quota": False' in authority
    assert '"idempotent_replays_consume_quota": False' in authority
    assert "key.usage_count += 1" not in authority.split("async def evaluation_key_runtime_status", 1)[1].split("async def update_evaluation_authority_key_lifecycle", 1)[0]


def test_customer_quota_reports_limit_used_remaining_and_semantics() -> None:
    authority = source(AUTHORITY)

    required = [
        '"limit": quota_limit',
        '"used": quota_used',
        '"remaining": quota_remaining',
        '"warning": quota_warning',
        '"semantics": "admitted_execution"',
        'credential_status = "quota_exhausted"',
        '"production_allowed": False',
        '"raw_secret_visible": False',
    ]
    for marker in required:
        assert marker in authority


def test_execution_status_is_scoped_to_current_key_and_does_not_expose_inputs() -> None:
    runtime = source(RUNTIME)
    delivery = source(DELIVERY)

    assert '@router.get("/executions/{execution_id}", response_model=dict)' in runtime
    assert "EvaluationRuntimeDelivery.api_key_id == api_key_id" in delivery
    assert "EvaluationRuntimeDelivery.grant_id == grant_id" in delivery
    assert "EvaluationRuntimeDelivery.owner_id_sha256 == _owner_digest(owner_id)" in delivery
    assert '"raw_task_input_persisted": False' in delivery
    assert '"raw_secret_visible": False' in delivery
    assert '"evidence_persisted"' in delivery


def test_task_execute_returns_current_quota_and_execution_status() -> None:
    runtime = source(RUNTIME)

    assert 'response["quota"] = snapshot["quota"]' in runtime
    assert 'response["execution_status"] = snapshot.get("latest_execution")' in runtime
    assert 'replay_response["quota"] = snapshot["quota"]' in runtime
    assert 'replay_response["idempotent_replay"] = True' in runtime


def test_customer_status_routes_are_canonically_registered() -> None:
    registry = source(REGISTRY)

    assert '"/evaluation/runtime/status"' in registry
    assert '"/evaluation/runtime/executions/{execution_id}"' in registry
    assert "evaluation_runtime_status" in registry
    assert "evaluation_runtime_execution_status" in registry


def test_customer_portal_shows_quota_and_execution_without_admin_access() -> None:
    html = source(PORTAL)
    js = source(PORTAL_JS)

    assert "Maestro External Evaluation" in html
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
    assert "audit-receipts?limit=20" in js
    assert "raw secret: no" in js
    assert "raw task input: no" in js
    assert "admitted executions used" in js
