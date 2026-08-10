from pathlib import Path


def _source() -> str:
    return Path("processual_api/static/js/admin_dashboard.js").read_text("utf-8")


def test_admin_dashboard_binds_execution_kpis_to_canonical_summary_route() -> None:
    source = _source()

    assert "/settings/execution-observability/summary?limit=20" in source
    assert "admin-card-execution-observability" in source
    assert "Task Execution Observability" in source
    assert "canonical execution records" in source
    assert "recent_executions" in source
    assert "success_rate_percent" in source
    assert "average_latency_ms" in source
    assert "No synthetic execution metrics are displayed" in source


def test_execution_observability_ui_exposes_execution_posture_and_traceability() -> None:
    source = _source()

    assert "Execution kind" in source
    assert "Environment" in source
    assert "Binding / Provider" in source
    assert "item.execution_kind" in source
    assert "item.environment" in source
    assert "item.binding_id" in source
    assert "item.execution_id" in source
    assert "by_execution_kind" in source
    assert "by_environment" in source
    assert "Showing " in source


def test_execution_observability_ui_matches_console_design_tokens() -> None:
    source = _source()

    assert "var(--surface-0)" in source
    assert "var(--surface-2)" in source
    assert "var(--rim)" in source
    assert "var(--ghost)" in source
    assert "var(--soft)" in source
    assert "var(--bright)" in source
    assert "var(--amber)" in source
    assert "var(--ok)" in source
    assert "var(--warn)" in source
    assert "var(--error)" in source
    assert "var(--font-data)" in source
    assert "var(--font-mono)" in source


def test_execution_observability_ui_has_responsive_and_accessible_states() -> None:
    source = _source()

    assert "@media (max-width:1100px)" in source
    assert "@media (max-width:720px)" in source
    assert 'aria-live="polite"' in source
    assert 'role="alert"' in source
    assert 'role="status"' in source
    assert 'aria-label="Recent task execution evidence"' in source
    assert 'tabindex="0"' in source
    assert "admin-exec-empty" in source
    assert "No execution evidence yet" in source


def test_system_health_is_not_presented_as_task_execution_evidence() -> None:
    source = _source()

    assert "System health is operational state" in source
    assert "not used as evidence that tasks executed successfully" in source
