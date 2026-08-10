from pathlib import Path


def test_admin_dashboard_binds_execution_kpis_to_canonical_summary_route() -> None:
    source = Path("processual_api/static/js/admin_dashboard.js").read_text("utf-8")

    assert "/settings/execution-observability/summary?limit=20" in source
    assert "admin-card-execution-observability" in source
    assert "Task Execution Observability" in source
    assert "canonical execution records" in source
    assert "recent_executions" in source
    assert "success_rate_percent" in source
    assert "average_latency_ms" in source
    assert "No synthetic execution metrics are displayed" in source


def test_system_health_is_not_presented_as_task_execution_evidence() -> None:
    source = Path("processual_api/static/js/admin_dashboard.js").read_text("utf-8")

    assert "System health is operational state" in source
    assert "not used as evidence that tasks executed successfully" in source
