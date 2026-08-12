from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit


def make_toolkit() -> AdaptiveGovernanceToolkit:
    toolkit = object.__new__(AdaptiveGovernanceToolkit)
    toolkit.kernel = Mock()
    toolkit.profile_task = Mock()
    toolkit.select_policy = Mock()
    toolkit.apply_policy_profile = Mock()
    toolkit.plan_tempo = Mock()
    toolkit.operating_contract = Mock()
    toolkit.enforce_budget_guard = Mock()
    toolkit.ledger = Mock()
    toolkit.maybe_checkpoint = Mock()
    toolkit._handle_cycle_patches = Mock()
    toolkit.strategy_bandit = Mock()
    toolkit.runtime_invariant_report = Mock()
    toolkit.quality_gate_report = Mock()
    toolkit.validate_operating_contract = Mock()
    toolkit.outcome_coverage_ratio = Mock(return_value=0.75)
    toolkit.convergence_monitor = Mock()
    toolkit.history_recorder = Mock()
    toolkit._record_history_event = Mock()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit._profiles = {}
    toolkit._policies = {}
    toolkit._checkpoint_drift_alerts = {}
    toolkit._checkpoint_handoff_suggestions = {}
    toolkit._checkpoint_critiques = {}
    toolkit._checkpoint_patches = {}
    toolkit._convergence_reports = {}
    toolkit._cycle_reports = []
    return toolkit


def cycle_dependencies(toolkit: AdaptiveGovernanceToolkit):
    workflow = SimpleNamespace(workflow_id="wf-1")
    profile = SimpleNamespace(name="profile")
    policy = SimpleNamespace(policy_version="policy-v1", min_sample_size=4)
    tempo = SimpleNamespace(name="tempo")
    contract = SimpleNamespace(name="contract")
    strategy = SimpleNamespace(name="strategy")
    invariants = SimpleNamespace(passed=True)
    quality_gate = SimpleNamespace(passed=True)
    contract_validation = SimpleNamespace(passed=True)
    convergence = SimpleNamespace(stable=True, window_size=3, recommendation="stable")
    history_event = SimpleNamespace(event_id="history-1")

    toolkit.kernel.get_workflow.return_value = workflow
    toolkit.profile_task.return_value = profile
    toolkit.select_policy.return_value = policy
    toolkit.plan_tempo.return_value = tempo
    toolkit.operating_contract.return_value = contract
    toolkit.strategy_bandit.suggest.return_value = strategy
    toolkit.runtime_invariant_report.return_value = invariants
    toolkit.quality_gate_report.return_value = quality_gate
    toolkit.validate_operating_contract.return_value = contract_validation
    toolkit.convergence_monitor.observe.return_value = convergence
    toolkit.history_recorder.record_cycle.return_value = history_event
    return (
        workflow,
        profile,
        policy,
        tempo,
        contract,
        strategy,
        invariants,
        quality_gate,
        contract_validation,
        convergence,
        history_event,
    )


def test_run_adaptive_cycle_minimal_path_skips_optional_mutations() -> None:
    toolkit = make_toolkit()
    (
        workflow,
        profile,
        policy,
        tempo,
        contract,
        strategy,
        invariants,
        quality_gate,
        contract_validation,
        convergence,
        history_event,
    ) = cycle_dependencies(toolkit)
    toolkit.maybe_checkpoint.return_value = None

    report = toolkit.run_adaptive_cycle(
        "wf-1",
        event="poll",
        milestone=False,
        final=False,
        now=12.0,
        apply_selected_policy=False,
        auto_apply_safe_patches=False,
    )

    toolkit.kernel.get_workflow.assert_called_once_with("wf-1")
    toolkit.profile_task.assert_called_once_with(workflow)
    toolkit.select_policy.assert_called_once_with(profile, workflow_id="wf-1")
    toolkit.apply_policy_profile.assert_not_called()
    toolkit.plan_tempo.assert_called_once_with(profile, policy, workflow_id="wf-1")
    toolkit.operating_contract.assert_called_once_with("wf-1", profile=profile, policy=policy, tempo=tempo)
    toolkit.enforce_budget_guard.assert_not_called()
    toolkit.kernel.observe_workflow.assert_not_called()
    toolkit.ledger.record.assert_not_called()
    toolkit.maybe_checkpoint.assert_called_once_with(
        "wf-1",
        profile=profile,
        policy=policy,
        event="poll",
        milestone=False,
        final=False,
        now=12.0,
    )
    toolkit._handle_cycle_patches.assert_called_once_with("wf-1", profile, policy, (), False)
    toolkit.strategy_bandit.suggest.assert_called_once_with(profile)
    toolkit.runtime_invariant_report.assert_called_once_with(
        "wf-1", profile=profile, policy=policy, auto_apply_requested=False
    )
    toolkit.quality_gate_report.assert_called_once_with("wf-1")
    toolkit.validate_operating_contract.assert_called_once_with(
        "wf-1",
        contract=contract,
        quality_gate=quality_gate,
        runtime_invariants=invariants,
        requested_action=None,
        auto_apply_requested=False,
    )
    assert report.workflow_id == "wf-1"
    assert report.profile is profile
    assert report.policy is policy
    assert report.tempo is tempo
    assert report.decision_id is None
    assert report.checkpoint is None
    assert report.strategy_suggestion is strategy
    assert report.runtime_invariants is invariants
    assert report.quality_gate is quality_gate
    assert report.operating_contract is contract
    assert report.contract_validation is contract_validation
    assert report.outcome_coverage_ratio == 0.75
    assert report.convergence_report is convergence
    assert toolkit._convergence_reports == {"wf-1": [convergence]}
    assert toolkit._cycle_reports == [report]
    toolkit.history_recorder.record_cycle.assert_called_once_with(report)
    toolkit._record_history_event.assert_called_once_with(history_event)
    toolkit._persist.assert_any_call("adaptive_convergence", convergence)
    toolkit._persist.assert_any_call("adaptive_cycles", report)
    cycle_audit = toolkit._audit_adaptive.call_args_list[-1]
    assert cycle_audit.args[1] == "wf-1"
    assert cycle_audit.args[2]["decision_id"] is None
    assert cycle_audit.args[2]["checkpoint_created"] is False
    assert cycle_audit.args[2]["patch_count"] == 0
    assert cycle_audit.args[2]["budget_action"] is None
    assert cycle_audit.args[2]["convergence_stable"] is True
    assert cycle_audit.args[2]["payload"] is report


def test_run_adaptive_cycle_full_path_records_decision_and_checkpoint_artifacts() -> None:
    toolkit = make_toolkit()
    (
        workflow,
        profile,
        policy,
        tempo,
        contract,
        strategy,
        invariants,
        quality_gate,
        contract_validation,
        convergence,
        history_event,
    ) = cycle_dependencies(toolkit)
    toolkit._profiles["wf-1"] = profile
    toolkit._policies["wf-1"] = policy
    telemetry = SimpleNamespace(source="telemetry")
    decision = SimpleNamespace(decision_id="decision-7")
    toolkit.kernel.observe_workflow.return_value = decision
    budget_action = SimpleNamespace(value="pause")
    toolkit.enforce_budget_guard.return_value = budget_action
    checkpoint = SimpleNamespace(checkpoint_number=2)
    toolkit.maybe_checkpoint.return_value = checkpoint
    drift_alerts = (SimpleNamespace(alert_id="d-1"), SimpleNamespace(alert_id="d-2"))
    handoff_suggestions = (SimpleNamespace(edge_id="e-1"),)
    critique = SimpleNamespace(findings=("finding",))
    patches = (SimpleNamespace(field="threshold"), SimpleNamespace(field="tempo"))
    toolkit._checkpoint_drift_alerts["wf-1"] = list(drift_alerts)
    toolkit._checkpoint_handoff_suggestions["wf-1"] = list(handoff_suggestions)
    toolkit._checkpoint_critiques["wf-1"] = [critique]
    toolkit._checkpoint_patches["wf-1"] = list(patches)

    report = toolkit.run_adaptive_cycle(
        "wf-1",
        telemetry=telemetry,
        event="milestone",
        milestone=True,
        final=True,
        now=99.0,
        cost_usage_ratio=0.9,
        apply_selected_policy=True,
        auto_apply_safe_patches=True,
    )

    toolkit.profile_task.assert_not_called()
    toolkit.select_policy.assert_not_called()
    toolkit.apply_policy_profile.assert_called_once_with(policy)
    toolkit.enforce_budget_guard.assert_called_once_with("wf-1", 0.9, profile, tempo)
    toolkit.kernel.observe_workflow.assert_called_once_with("wf-1", telemetry)
    toolkit.ledger.record.assert_called_once_with(
        decision, workflow_id="wf-1", important=True, source="adaptive_cycle"
    )
    toolkit.maybe_checkpoint.assert_called_once_with(
        "wf-1",
        profile=profile,
        policy=policy,
        event="milestone",
        milestone=True,
        final=True,
        now=99.0,
    )
    toolkit._handle_cycle_patches.assert_called_once_with("wf-1", profile, policy, patches, True)
    toolkit.runtime_invariant_report.assert_called_once_with(
        "wf-1", profile=profile, policy=policy, auto_apply_requested=True
    )
    toolkit.validate_operating_contract.assert_called_once_with(
        "wf-1",
        contract=contract,
        quality_gate=quality_gate,
        runtime_invariants=invariants,
        requested_action=budget_action,
        auto_apply_requested=True,
    )
    assert report.decision_id == "decision-7"
    assert report.checkpoint is checkpoint
    assert report.drift_alerts == drift_alerts
    assert report.handoff_suggestions == handoff_suggestions
    assert report.policy_critique is critique
    assert report.policy_patches == patches
    assert report.budget_action is budget_action
    assert report.convergence_report is convergence
    toolkit.history_recorder.record_cycle.assert_called_once_with(report)
    toolkit._record_history_event.assert_called_once_with(history_event)
    cycle_audit = toolkit._audit_adaptive.call_args_list[-1]
    assert cycle_audit.args[2]["decision_id"] == "decision-7"
    assert cycle_audit.args[2]["checkpoint_created"] is True
    assert cycle_audit.args[2]["drift_alert_count"] == 2
    assert cycle_audit.args[2]["handoff_suggestion_count"] == 1
    assert cycle_audit.args[2]["patch_count"] == 2
    assert cycle_audit.args[2]["budget_action"] == "pause"
    assert cycle_audit.args[2]["runtime_invariants_passed"] is True
    assert cycle_audit.args[2]["quality_gate_passed"] is True
    assert cycle_audit.args[2]["contract_passed"] is True


def test_pulse_adaptive_delegates_to_run_adaptive_cycle() -> None:
    toolkit = object.__new__(AdaptiveGovernanceToolkit)
    toolkit.run_adaptive_cycle = Mock(return_value=SimpleNamespace(workflow_id="wf-1"))

    result = toolkit.pulse_adaptive("wf-1", event="tick", final=True)

    assert result.workflow_id == "wf-1"
    toolkit.run_adaptive_cycle.assert_called_once_with("wf-1", event="tick", final=True)
