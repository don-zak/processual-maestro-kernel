from types import SimpleNamespace

from processual_kernel.adaptive.efficiency import AdaptiveEfficiencyGovernor


def test_efficiency_report_returns_idle_recommendation_when_no_signals() -> None:
    report = AdaptiveEfficiencyGovernor().efficiency_report("wf-1")

    assert report.workflow_id == "wf-1"
    assert report.checkpoint_coalesced_count == 0
    assert report.duplicate_runtime_command_count == 0
    assert report.runtime_command_count == 0
    assert report.auto_outcome_evaluated_count == 0
    assert report.auto_outcome_skipped_count == 0
    assert report.checkpoint_backpressure_count == 0
    assert report.runtime_batch_suppressed_count == 0
    assert report.runtime_conflict_suppressed_count == 0
    assert report.outcome_sweep_planned_count == 0
    assert report.outcome_sweep_deferred_count == 0
    assert report.workload_budget_blocked_count == 0
    assert report.evidence_digest_count == 0
    assert report.runtime_throttle_suppressed_count == 0
    assert report.evidence_delta_count == 0
    assert report.encrypted_report_count == 0
    assert report.encrypted_report_index_count == 0
    assert report.ui_snapshot_count == 0
    assert report.recommendations == ("efficiency guardrails found no duplicate adaptive work",)


def test_efficiency_report_aggregates_counts_and_all_recommendation_branches() -> None:
    governor = AdaptiveEfficiencyGovernor()

    report = governor.efficiency_report(
        "wf-1",
        checkpoint_coalescing=[SimpleNamespace(coalesced=True), SimpleNamespace(coalesced=False)],
        runtime_deduplication=[SimpleNamespace(duplicate=True), SimpleNamespace(duplicate=False)],
        runtime_results=[SimpleNamespace(), SimpleNamespace(), SimpleNamespace()],
        auto_outcomes=[
            SimpleNamespace(evaluated_count=2, skipped_count=1),
            SimpleNamespace(evaluated_count=3, skipped_count=2),
        ],
        checkpoint_backpressure=[SimpleNamespace(active=True), SimpleNamespace(active=False)],
        runtime_batches=[SimpleNamespace(suppressed_count=2), SimpleNamespace(suppressed_count=1)],
        outcome_sweep_plans=[
            SimpleNamespace(batch_size=4, remaining_count=2, deferred_count=1),
            SimpleNamespace(batch_size=1, remaining_count=0, deferred_count=2),
        ],
        workload_budgets=[SimpleNamespace(allowed=False), SimpleNamespace(allowed=True)],
        runtime_conflicts=[SimpleNamespace(conflicting_count=2), SimpleNamespace(conflicting_count=0)],
        evidence_digests=[SimpleNamespace(), SimpleNamespace()],
        runtime_throttles=[
            SimpleNamespace(suppressed_indices=(0, 2)),
            SimpleNamespace(suppressed_indices=()),
        ],
        evidence_deltas=[SimpleNamespace()],
        encrypted_reports=[SimpleNamespace(), SimpleNamespace(), SimpleNamespace()],
        encrypted_report_indexes=[SimpleNamespace()],
        ui_snapshots=[SimpleNamespace(), SimpleNamespace()],
    )

    assert report.checkpoint_coalesced_count == 1
    assert report.duplicate_runtime_command_count == 1
    assert report.runtime_command_count == 3
    assert report.auto_outcome_evaluated_count == 5
    assert report.auto_outcome_skipped_count == 3
    assert report.checkpoint_backpressure_count == 1
    assert report.runtime_batch_suppressed_count == 3
    assert report.runtime_conflict_suppressed_count == 2
    assert report.outcome_sweep_planned_count == 5
    assert report.outcome_sweep_deferred_count == 3
    assert report.workload_budget_blocked_count == 1
    assert report.evidence_digest_count == 2
    assert report.runtime_throttle_suppressed_count == 2
    assert report.evidence_delta_count == 1
    assert report.encrypted_report_count == 3
    assert report.encrypted_report_index_count == 1
    assert report.ui_snapshot_count == 2

    assert report.recommendations == (
        "keep checkpoint coalescing enabled to avoid duplicate adaptive cycles",
        "honor checkpoint backpressure hints before re-polling schedule state",
        "keep runtime command idempotency keys stable across retries",
        "keep mutating runtime command batches small and idempotent",
        "re-run outcome sweep after the minimum age window expires",
        "continue outcome sweeps in bounded batches until coverage is complete",
        "respect outcome age windows and retry deferred outcomes later",
        "resolve conflicting runtime recommendations before executing mutating commands",
        "defer optional adaptive work until workload budget is replenished",
        "use evidence digests for lightweight review before opening full artifacts",
        "honor runtime command throttle plans to avoid rapid mutable action churn",
        "use evidence deltas to review only changed artifacts between evidence packs",
        "keep sensitive adaptive reports encrypted with externally managed AES-256 keys",
        "use encrypted report indexes for lightweight review without decrypting reports",
        "use UI snapshots for safe offline review before opening full evidence packs",
    )


def test_efficiency_report_avoids_recommendations_for_non_triggering_inputs() -> None:
    report = AdaptiveEfficiencyGovernor().efficiency_report(
        "wf-2",
        checkpoint_coalescing=[SimpleNamespace(coalesced=False)],
        runtime_deduplication=[SimpleNamespace(duplicate=False)],
        runtime_results=[SimpleNamespace()],
        auto_outcomes=[SimpleNamespace(evaluated_count=1, skipped_count=0)],
        checkpoint_backpressure=[SimpleNamespace(active=False)],
        runtime_batches=[SimpleNamespace(suppressed_count=0)],
        outcome_sweep_plans=[SimpleNamespace(batch_size=1, remaining_count=0, deferred_count=0)],
        workload_budgets=[SimpleNamespace(allowed=True)],
        runtime_conflicts=[SimpleNamespace(conflicting_count=0)],
        runtime_throttles=[SimpleNamespace(suppressed_indices=())],
    )

    assert report.runtime_command_count == 1
    assert report.auto_outcome_evaluated_count == 1
    assert report.outcome_sweep_planned_count == 1
    assert report.recommendations == ("efficiency guardrails found no duplicate adaptive work",)
