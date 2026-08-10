from processual_api.services.execution_observability import (
    clear_execution_observations_for_tests,
    execution_observability_snapshot,
    record_execution_observation,
)


def setup_function() -> None:
    clear_execution_observations_for_tests()


def teardown_function() -> None:
    clear_execution_observations_for_tests()


def test_snapshot_reconciles_aggregates_from_same_execution_records() -> None:
    first = record_execution_observation(
        execution_kind="workflow",
        task_id="workflow.llm_orchestration",
        provider="openai",
        status="success",
        duration_ms=100.0,
        items_total=3,
        items_succeeded=3,
        items_failed=0,
        paced=False,
        plan_reason="shared_governor_only",
    )
    second = record_execution_observation(
        execution_kind="workflow",
        task_id="workflow.llm_orchestration",
        provider="openai",
        status="partial_error",
        duration_ms=300.0,
        items_total=2,
        items_succeeded=1,
        items_failed=1,
        paced=True,
        plan_reason="broad_single_provider",
        failure_stage="execution",
        failure_code="item_execution_error",
    )

    snapshot = execution_observability_snapshot(limit=10)

    assert snapshot["source_of_truth"] == "canonical_execution_records"
    assert snapshot["record_count"] == 2
    assert snapshot["summary"] == {
        "executions_total": 2,
        "executions_completed": 2,
        "executions_succeeded": 1,
        "executions_failed": 0,
        "executions_partial_error": 1,
        "success_rate_percent": 50.0,
        "average_latency_ms": 200.0,
        "items_total": 5,
        "items_succeeded": 4,
        "items_failed": 1,
    }
    assert snapshot["by_task"] == {"workflow.llm_orchestration": 2}
    assert snapshot["by_provider"] == {"openai": 2}
    assert snapshot["by_status"] == {"partial_error": 1, "success": 1}
    assert snapshot["by_execution_kind"] == {"workflow": 2}
    assert snapshot["by_environment"] == {"runtime": 2}
    assert snapshot["reconciliation"]["aggregate_record_count"] == len(
        snapshot["recent_executions"]
    )
    assert snapshot["reconciliation"]["aggregates_derived_from_records"] is True
    assert {item["execution_id"] for item in snapshot["recent_executions"]} == {
        first["execution_id"],
        second["execution_id"],
    }


def test_record_rejects_outcomes_exceeding_total() -> None:
    try:
        record_execution_observation(
            execution_kind="task",
            task_id="invalid",
            status="failed",
            duration_ms=1,
            items_total=1,
            items_succeeded=1,
            items_failed=1,
        )
    except ValueError as exc:
        assert "cannot exceed" in str(exc)
    else:
        raise AssertionError("invalid execution outcomes must fail closed")


def test_record_rejects_non_terminal_status() -> None:
    try:
        record_execution_observation(
            execution_kind="task",
            task_id="invalid",
            status="running",
            duration_ms=1,
            items_total=1,
        )
    except ValueError as exc:
        assert "status must be terminal" in str(exc)
    else:
        raise AssertionError("non-terminal execution status must fail closed")


def test_record_rejects_inconsistent_terminal_outcome_semantics() -> None:
    cases = [
        {"status": "success", "items_succeeded": 0, "items_failed": 1},
        {"status": "failed", "items_succeeded": 0, "items_failed": 0},
        {"status": "partial_error", "items_succeeded": 1, "items_failed": 0},
    ]
    for case in cases:
        try:
            record_execution_observation(
                execution_kind="task",
                task_id="invalid",
                duration_ms=1,
                items_total=1,
                **case,
            )
        except ValueError:
            continue
        raise AssertionError(f"inconsistent terminal outcome must fail closed: {case}")


def test_snapshot_recent_limit_does_not_change_aggregate_truth() -> None:
    for index in range(5):
        record_execution_observation(
            execution_kind="task",
            task_id=f"task.{index}",
            status="success",
            duration_ms=index + 1,
            items_total=1,
            items_succeeded=1,
        )

    snapshot = execution_observability_snapshot(limit=2)

    assert snapshot["record_count"] == 5
    assert snapshot["summary"]["executions_total"] == 5
    assert snapshot["by_execution_kind"] == {"task": 5}
    assert snapshot["by_environment"] == {"runtime": 5}
    assert len(snapshot["recent_executions"]) == 2
    assert snapshot["reconciliation"]["aggregate_record_count"] == 5
    assert snapshot["reconciliation"]["recent_count"] == 2
