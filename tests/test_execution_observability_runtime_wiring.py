from pathlib import Path

from processual_api.main import app


def test_execution_observability_summary_route_is_registered_once() -> None:
    paths = [route.path for route in app.routes]
    assert paths.count("/settings/execution-observability/summary") == 1


def test_llm_orchestration_records_canonical_execution_and_returns_id() -> None:
    source = Path("processual_api/routers/workflows.py").read_text("utf-8")

    assert "record_execution_observation(" in source
    assert 'task_id="workflow.llm_orchestration"' in source
    assert 'status="saturated"' in source
    assert 'terminal_status = "partial_error" if error_items else "success"' in source
    assert '"execution_id": execution["execution_id"]' in source
    assert 'failure_code="execution_fanout_saturated"' in source
