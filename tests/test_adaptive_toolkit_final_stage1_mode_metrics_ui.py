from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit
from processual_kernel.adaptive_types import RuntimeMode


def make_toolkit() -> AdaptiveGovernanceToolkit:
    toolkit = object.__new__(AdaptiveGovernanceToolkit)
    toolkit.kernel = Mock()
    toolkit.metrics_collector = Mock()
    toolkit.quality_gates = Mock()
    toolkit.operations_governor = Mock()
    toolkit.calibrator = Mock()
    toolkit.efficiency_governor = Mock()
    toolkit.profile_task = Mock()
    toolkit.select_policy = Mock()
    toolkit.runtime_invariant_report = Mock()
    toolkit.request_human_approval = Mock()
    toolkit.rollback_policy_patch = Mock()
    toolkit.build_adaptive_evidence_pack = Mock()
    toolkit.adaptive_evidence_digest = Mock()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit._profiles = {}
    toolkit._policies = {}
    toolkit._checkpoint_reports = {}
    toolkit._successful_patch_versions = set()
    toolkit._encrypted_reports = {}
    toolkit._encrypted_report_indexes = {}
    toolkit._ui_snapshots = {}
    toolkit._checkpoint_coalescing_decisions = {}
    toolkit._runtime_deduplication_results = {}
    toolkit._runtime_command_results = {}
    toolkit._auto_outcome_reports = {}
    toolkit._checkpoint_backpressure_hints = {}
    toolkit._runtime_batch_plans = {}
    toolkit._outcome_sweep_plans = {}
    toolkit._workload_budget_decisions = {}
    toolkit._runtime_conflict_plans = {}
    toolkit._evidence_digests = {}
    toolkit._runtime_throttle_plans = {}
    toolkit._evidence_deltas = {}
    toolkit._efficiency_reports = {}
    toolkit.evaluator = SimpleNamespace(outcomes={})
    toolkit.ledger = SimpleNamespace(name="ledger")
    toolkit.mode = RuntimeMode.OBSERVE
    return toolkit


def test_metrics_snapshot_flattens_checkpoints_and_records_snapshot() -> None:
    toolkit = make_toolkit()
    first = SimpleNamespace(name="first")
    second = SimpleNamespace(name="second")
    toolkit._checkpoint_reports = {"wf-1": [first], "wf-2": [second]}
    toolkit.evaluator.outcomes = {"d1": SimpleNamespace(decision_quality=0.7)}
    toolkit.calibrator.applied_patches = [SimpleNamespace(field="threshold")]
    snapshot = SimpleNamespace(outcome_coverage_ratio=0.9)
    toolkit.metrics_collector.snapshot.return_value = snapshot

    result = toolkit.metrics_snapshot()

    assert result is snapshot
    kwargs = toolkit.metrics_collector.snapshot.call_args.kwargs
    assert kwargs["checkpoints"] == [first, second]
    assert list(kwargs["outcomes"]) == list(toolkit.evaluator.outcomes.values())
    assert kwargs["ledger"] is toolkit.ledger
    assert kwargs["applied_patches"] == toolkit.calibrator.applied_patches
    assert kwargs["successful_patch_versions"] == set()
    toolkit._persist.assert_called_once_with("metrics_snapshots", snapshot)


def test_propose_runtime_mode_transition_resolves_string_and_forwards_evidence() -> None:
    toolkit = make_toolkit()
    metrics = SimpleNamespace(name="metrics")
    gate = SimpleNamespace(eligible_next_mode=RuntimeMode.RECOMMEND)
    profile = SimpleNamespace(risk=SimpleNamespace(value="medium"))
    policy = SimpleNamespace(name="policy")
    invariants = SimpleNamespace(passed=True)
    decision = SimpleNamespace(
        workflow_id="wf-1",
        current_mode=RuntimeMode.OBSERVE,
        requested_mode=RuntimeMode.CONTROLLED_ADAPTIVE,
        allowed=True,
        required_human_approval=False,
        violations=(),
    )
    toolkit.metrics_snapshot = Mock(return_value=metrics)
    toolkit.quality_gate_report = Mock(return_value=gate)
    toolkit.kernel.get_workflow.return_value = SimpleNamespace(workflow_id="wf-1")
    toolkit.profile_task.return_value = profile
    toolkit.select_policy.return_value = policy
    toolkit.runtime_invariant_report.return_value = invariants
    toolkit.pending_outcomes = Mock(return_value=("pending",))
    toolkit.pending_approval_requests = Mock(return_value=("approval", "approval-2"))
    toolkit.operations_governor.decide_mode_transition.return_value = decision

    result = toolkit.propose_runtime_mode_transition("wf-1", requested_mode="controlled_adaptive")

    assert result is decision
    toolkit.quality_gate_report.assert_called_once_with("wf-1", metrics=metrics)
    toolkit.runtime_invariant_report.assert_called_once_with("wf-1", profile=profile, policy=policy)
    toolkit.operations_governor.decide_mode_transition.assert_called_once_with(
        workflow_id="wf-1",
        current_mode=RuntimeMode.OBSERVE,
        requested_mode=RuntimeMode.CONTROLLED_ADAPTIVE,
        profile=profile,
        quality_gate=gate,
        runtime_invariants=invariants,
        metrics=metrics,
        pending_outcome_count=1,
        pending_approval_count=2,
    )
    toolkit._persist.assert_called_once_with("mode_transitions", decision)


def test_apply_runtime_mode_transition_blocks_or_updates_both_modes() -> None:
    toolkit = make_toolkit()
    blocked = SimpleNamespace(
        workflow_id="wf-blocked",
        current_mode=RuntimeMode.OBSERVE,
        requested_mode=RuntimeMode.RECOMMEND,
        allowed=False,
        required_human_approval=True,
        reason="human approval required",
    )

    with pytest.raises(RuntimeError, match="human approval required"):
        toolkit.apply_runtime_mode_transition(blocked)

    toolkit.request_human_approval.assert_called_once_with(
        "wf-blocked",
        "runtime_mode_transition",
        "human approval required",
        requested_mode="recommend",
        current_mode="observe",
    )
    assert toolkit.mode is RuntimeMode.OBSERVE

    allowed = SimpleNamespace(
        workflow_id="wf-allowed",
        current_mode=RuntimeMode.OBSERVE,
        requested_mode=RuntimeMode.RECOMMEND,
        allowed=True,
        required_human_approval=False,
        reason="safe",
    )
    assert toolkit.apply_runtime_mode_transition(allowed) is RuntimeMode.RECOMMEND
    assert toolkit.mode is RuntimeMode.RECOMMEND
    assert toolkit.calibrator.mode is RuntimeMode.RECOMMEND
    assert toolkit._audit_adaptive.call_args.args[2]["applied"] is True


def test_verify_applied_patches_uses_recent_quality_and_rolls_back_regression() -> None:
    toolkit = make_toolkit()
    toolkit.evaluator.outcomes = {
        "older": SimpleNamespace(decision_quality=0.61),
        "latest": SimpleNamespace(decision_quality=0.42),
    }
    patch_good = SimpleNamespace(field="retries", policy_version_to="v2")
    patch_bad = SimpleNamespace(field="threshold", policy_version_to="v3")
    toolkit.calibrator.applied_patches = [patch_good, patch_bad]
    metrics = SimpleNamespace(name="metrics")
    toolkit.metrics_snapshot = Mock(return_value=metrics)
    results = (
        SimpleNamespace(
            patch=patch_good,
            status="verified",
            rollback_recommended=False,
            confidence=0.9,
        ),
        SimpleNamespace(
            patch=patch_bad,
            status="regression",
            rollback_recommended=True,
            confidence=0.95,
        ),
    )
    toolkit.operations_governor.verify_patches.return_value = results

    assert toolkit.verify_applied_patches(
        "wf-1", rollback_on_regression=True, min_decision_quality=0.55
    ) == results

    toolkit.operations_governor.verify_patches.assert_called_once_with(
        workflow_id="wf-1",
        patches=toolkit.calibrator.applied_patches,
        metrics=metrics,
        recent_decision_quality=0.42,
        min_decision_quality=0.55,
    )
    toolkit.rollback_policy_patch.assert_called_once_with(patch_bad)
    assert toolkit._persist.call_count == 2


def test_encrypted_index_and_ui_snapshot_use_cached_artifacts() -> None:
    toolkit = make_toolkit()
    encrypted = SimpleNamespace(report_kind="adaptive_report")
    toolkit._encrypted_reports["wf-1"] = [encrypted]
    index = SimpleNamespace(encrypted_count=1, schema_version="1.0")
    toolkit.efficiency_governor.encrypted_report_index.return_value = index

    assert toolkit.adaptive_encrypted_report_index("wf-1") is index
    toolkit.efficiency_governor.encrypted_report_index.assert_called_once_with("wf-1", (encrypted,))
    assert toolkit._encrypted_report_indexes == {"wf-1": [index]}

    pack = SimpleNamespace(workflow_id="wf-1")
    digest = SimpleNamespace(schema_version="1.0")
    snapshot = SimpleNamespace(
        status="ready", schema_version="1.0", encrypted_report_count=1
    )
    toolkit.build_adaptive_evidence_pack.return_value = pack
    toolkit.adaptive_evidence_digest.return_value = digest
    toolkit.efficiency_governor.ui_snapshot_from_evidence_pack.return_value = snapshot

    assert toolkit.adaptive_ui_snapshot("wf-1", max_recommendations=4) is snapshot
    toolkit.efficiency_governor.ui_snapshot_from_evidence_pack.assert_called_once_with(
        pack,
        digest=digest,
        encrypted_index=index,
        max_recommendations=4,
    )
    assert toolkit._ui_snapshots == {"wf-1": [snapshot]}


def test_adaptive_efficiency_report_forwards_all_accumulated_artifacts() -> None:
    toolkit = make_toolkit()
    workflow_id = "wf-1"
    toolkit._checkpoint_coalescing_decisions[workflow_id] = ["coalesce"]
    toolkit._runtime_deduplication_results[workflow_id] = ["dedupe"]
    toolkit._runtime_command_results[workflow_id] = ["runtime"]
    toolkit._auto_outcome_reports[workflow_id] = ["outcome"]
    toolkit._checkpoint_backpressure_hints[workflow_id] = ["backpressure"]
    toolkit._runtime_batch_plans[workflow_id] = ["batch"]
    toolkit._outcome_sweep_plans[workflow_id] = ["sweep"]
    toolkit._workload_budget_decisions[workflow_id] = ["budget"]
    toolkit._runtime_conflict_plans[workflow_id] = ["conflict"]
    toolkit._evidence_digests[workflow_id] = ["digest"]
    toolkit._runtime_throttle_plans[workflow_id] = ["throttle"]
    toolkit._evidence_deltas[workflow_id] = ["delta"]
    toolkit._encrypted_reports[workflow_id] = ["encrypted"]
    toolkit._encrypted_report_indexes[workflow_id] = ["index"]
    toolkit._ui_snapshots[workflow_id] = ["ui"]
    report = SimpleNamespace(
        checkpoint_coalesced_count=1,
        duplicate_runtime_command_count=2,
        runtime_command_count=3,
        checkpoint_backpressure_count=4,
        runtime_batch_suppressed_count=5,
        outcome_sweep_planned_count=6,
        outcome_sweep_deferred_count=7,
        workload_budget_blocked_count=8,
        runtime_conflict_suppressed_count=9,
        evidence_digest_count=10,
        runtime_throttle_suppressed_count=11,
        evidence_delta_count=12,
        encrypted_report_count=13,
        encrypted_report_index_count=14,
        ui_snapshot_count=15,
    )
    toolkit.efficiency_governor.efficiency_report.return_value = report

    assert toolkit.adaptive_efficiency_report(workflow_id) is report
    kwargs = toolkit.efficiency_governor.efficiency_report.call_args.kwargs
    assert kwargs["workflow_id"] == workflow_id
    assert kwargs["checkpoint_coalescing"] == ["coalesce"]
    assert kwargs["runtime_deduplication"] == ["dedupe"]
    assert kwargs["runtime_results"] == ["runtime"]
    assert kwargs["runtime_conflicts"] == ["conflict"]
    assert kwargs["ui_snapshots"] == ["ui"]
    assert toolkit._efficiency_reports == {workflow_id: [report]}
    toolkit._persist.assert_called_once_with("adaptive_efficiency_reports", report)
