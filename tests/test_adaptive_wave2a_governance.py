from types import SimpleNamespace

from processual_kernel.adaptive.certification import AdaptiveCertificationAuthority, checksum
from processual_kernel.adaptive.checkpoints import CheckpointScheduler
from processual_kernel.adaptive.contracts import AdaptiveOperatingContractManager
from processual_kernel.adaptive.ops_governance import AdaptiveOperationsGovernor
from processual_kernel.adaptive.replay_lab import ReplayLab
from processual_kernel.adaptive_types import (
    AdaptiveEvidencePack,
    AdaptiveQualityGateReport,
    AgentCountBand,
    AmbiguityLevel,
    CertificationLevel,
    CheckpointKind,
    DecisionOutcome,
    ExecutionTempo,
    MetricsSnapshot,
    PolicyName,
    PolicyPatch,
    PolicyProfile,
    RiskLevel,
    RuntimeInvariantReport,
    RuntimeMode,
    TaskDuration,
    TaskProfile,
    TaskSize,
    TempoPlan,
    WorkflowHistoryEvent,
)
from processual_kernel.types import (
    AgentState,
    KernelPolicy,
    MaestroAction,
    StepRecord,
    StepState,
    WorkflowPlan,
    WorkflowRecord,
    WorkflowState,
    WorkflowStep,
)


def _profile(risk: RiskLevel = RiskLevel.LOW, *, audit: bool = True) -> TaskProfile:
    return TaskProfile(
        size=TaskSize.MEDIUM,
        duration=TaskDuration.LONG,
        risk=risk,
        ambiguity=AmbiguityLevel.MEDIUM,
        agent_count=AgentCountBand.FEW,
        requires_audit=audit,
    )


def _policy(
    name: PolicyName = PolicyName.BALANCED,
    *,
    mode: RuntimeMode = RuntimeMode.RECOMMEND,
    min_edge_psi: float = -0.04,
    max_retries: int = 2,
    human_gate_required: bool = False,
) -> PolicyProfile:
    return PolicyProfile(
        name=name,
        policy_version="test-1",
        kernel_policy=KernelPolicy(min_edge_psi=min_edge_psi),
        checkpoint_interval_minutes=60,
        runtime_mode=mode,
        max_agents=4,
        max_retries=max_retries,
        parallel_execution=True,
        drift_sensitivity=0.2,
        min_sample_size=3,
        human_gate_required=human_gate_required,
    )


def _tempo(interval: int | None = 60) -> TempoPlan:
    return TempoPlan(
        tempo=ExecutionTempo.BALANCED,
        max_agents=4,
        max_retries=2,
        allow_parallel_execution=True,
        checkpoint_interval_minutes=interval,
        monitor_drift=True,
        budget_stop_threshold=0.9,
    )


def _metrics(
    *,
    patch_success: float = 0.9,
    false_retry: float = 0.0,
    false_reroute: float = 0.0,
    handoff_failure: float = 0.0,
    outcome_coverage: float = 1.0,
    workflow_count: int = 3,
) -> MetricsSnapshot:
    return MetricsSnapshot(
        workflow_success_rate=0.9,
        handoff_failure_rate=handoff_failure,
        recovery_time=1.0,
        cost_per_successful_workflow=1.0,
        false_retry_rate=false_retry,
        false_reroute_rate=false_reroute,
        late_escalation_rate=0.0,
        unnecessary_escalation_rate=0.0,
        agent_bloat_ratio=0.0,
        checkpoint_detection_accuracy=0.9,
        policy_patch_success_rate=patch_success,
        outcome_coverage_ratio=outcome_coverage,
        workflow_count=workflow_count,
        decision_outcome_count=3,
        checkpoint_count=2,
    )


def _quality_gate(
    *,
    passed: bool = True,
    eligible: RuntimeMode | None = RuntimeMode.CONTROLLED_ADAPTIVE,
    metrics: MetricsSnapshot | None = None,
    pending_outcomes: int = 0,
    pending_approvals: int = 0,
) -> AdaptiveQualityGateReport:
    return AdaptiveQualityGateReport(
        workflow_id="wf",
        runtime_mode=RuntimeMode.RECOMMEND,
        passed=passed,
        violations=() if passed else ("gate failed",),
        eligible_next_mode=eligible,
        metrics=metrics or _metrics(),
        pending_outcome_count=pending_outcomes,
        pending_approval_count=pending_approvals,
    )


def _invariants(*, passed: bool = True) -> RuntimeInvariantReport:
    return RuntimeInvariantReport(
        workflow_id="wf",
        passed=passed,
        checked_invariants=("boundary",),
        violations=() if passed else ("boundary violation",),
    )


def _patch(*, reversible: bool = True, field: str = "max_retries") -> PolicyPatch:
    return PolicyPatch(
        field=field,
        old_value=1,
        new_value=2,
        reason="test",
        policy_version_from="test-1",
        policy_version_to="test-2",
        sample_size=5,
        reversible=reversible,
    )


def _evidence_pack(
    *,
    runtime_mode: RuntimeMode = RuntimeMode.RECOMMEND,
    q_passed: bool = True,
    invariants_passed: bool = True,
    contract_passed: bool = True,
    convergence_stable: bool = True,
    pending_outcomes: int = 0,
    pending_approvals: int = 0,
) -> AdaptiveEvidencePack:
    quality_gate = _quality_gate(
        passed=q_passed,
        pending_outcomes=pending_outcomes,
        pending_approvals=pending_approvals,
    )
    artifacts = {
        "profile": {"risk": "low"},
        "policy": {"runtime_mode": runtime_mode.value},
        "tempo": {"tempo": "balanced"},
        "metrics": {},
        "quality_gate": quality_gate,
        "runtime_invariants": _invariants(passed=invariants_passed),
        "checkpoints": [],
        "policy_patches": [],
        "history": [],
        "contract_validation": {"passed": contract_passed},
        "convergence_report": {"stable": convergence_stable},
        "approvals": [],
    }
    return AdaptiveEvidencePack(
        workflow_id="wf",
        counts={
            "checkpoints": 0,
            "policy_patches": 0,
            "history_events": 0,
            "approvals": pending_approvals,
        },
        artifacts=artifacts,
    )


def test_ops_governor_blocks_controlled_adaptive_on_combined_safety_evidence():
    governor = AdaptiveOperationsGovernor()
    decision = governor.decide_mode_transition(
        workflow_id="wf",
        current_mode=RuntimeMode.RECOMMEND,
        requested_mode=RuntimeMode.CONTROLLED_ADAPTIVE,
        profile=_profile(RiskLevel.LOW),
        quality_gate=_quality_gate(passed=False),
        runtime_invariants=_invariants(passed=False),
        metrics=_metrics(patch_success=0.4),
        pending_outcome_count=2,
        pending_approval_count=1,
    )

    assert decision.allowed is False
    assert decision.required_human_approval is False
    assert decision.reason == "transition blocked by safety evidence"
    assert "quality gate: gate failed" in decision.violations
    assert "runtime invariant: boundary violation" in decision.violations
    assert "all important decisions need outcomes before controlled adaptation" in decision.violations
    assert "pending human approvals must be resolved before controlled adaptation" in decision.violations
    assert "policy patch success rate is too low for controlled adaptation" in decision.violations


def test_ops_governor_requires_human_approval_for_high_risk_non_controlled_transition():
    governor = AdaptiveOperationsGovernor()
    decision = governor.decide_mode_transition(
        workflow_id="wf",
        current_mode=RuntimeMode.OBSERVE,
        requested_mode=RuntimeMode.RECOMMEND,
        profile=_profile(RiskLevel.HIGH),
        quality_gate=_quality_gate(),
        runtime_invariants=_invariants(),
        metrics=_metrics(workflow_count=0),
        pending_outcome_count=0,
        pending_approval_count=0,
    )

    assert decision.allowed is False
    assert decision.required_human_approval is True
    assert decision.reason == "transition requires human approval"
    assert "human approval is required before applying this transition" in decision.warnings
    assert "promotion to recommend has no workflow evidence yet" in decision.warnings


def test_ops_governor_patch_verification_covers_verified_rollback_and_more_evidence():
    governor = AdaptiveOperationsGovernor()

    verified = governor.verify_patches("wf", [_patch()], _metrics(), recent_decision_quality=1.2)[0]
    assert verified.status == "verified"
    assert verified.rollback_recommended is False
    assert verified.confidence == 0.95

    rollback = governor.verify_patches(
        "wf",
        [_patch(reversible=True)],
        _metrics(false_retry=0.4, false_reroute=0.4, handoff_failure=0.5, outcome_coverage=0.7),
        recent_decision_quality=0.4,
    )[0]
    assert rollback.status == "rollback_recommended"
    assert rollback.rollback_recommended is True
    assert "recent decision quality" in rollback.reason
    assert "false retry rate" in rollback.reason
    assert rollback.confidence == 0.4

    observe = governor.verify_patches(
        "wf",
        [_patch(reversible=False)],
        _metrics(false_retry=0.4, patch_success=0.5),
    )[0]
    assert observe.status == "needs_more_evidence"
    assert observe.rollback_recommended is False


def test_checkpoint_kind_precedence_and_action_selection():
    scheduler = CheckpointScheduler()
    profile = _profile()
    policy = _policy()

    assert scheduler._checkpoint_kind("wf", profile, policy, "repeated_failure", True, True, 100.0) == CheckpointKind.FINAL
    assert scheduler._checkpoint_kind("wf", profile, policy, "repeated_failure", True, False, 100.0) == CheckpointKind.EVENT_BASED
    assert scheduler._checkpoint_kind("wf", profile, policy, None, True, False, 100.0) == CheckpointKind.MILESTONE
    assert scheduler._checkpoint_kind("wf", profile, policy, None, False, False, 100.0) == CheckpointKind.HOURLY

    scheduler._last_checkpoint_at["wf"] = 100.0
    assert scheduler._checkpoint_kind("wf", profile, policy, None, False, False, 120.0) is None
    assert scheduler._checkpoint_kind("wf", profile, policy, None, False, False, 3700.0) == CheckpointKind.HOURLY

    plan = WorkflowPlan(workflow_id="wf", goal="test", steps=(WorkflowStep("s1", "x", "do"),))
    workflow = WorkflowRecord(plan=plan, state=WorkflowState.COMPLETED)
    workflow.steps["s1"] = StepRecord(step=plan.steps[0], state=StepState.COMPLETED)
    assert scheduler._recommended_action(workflow, [], profile) == MaestroAction.FINALIZE
    assert scheduler._recommended_action(workflow, ["failed_steps:s1"], profile) == MaestroAction.REROUTE
    assert scheduler._recommended_action(workflow, ["profile_risk:critical"], _profile(RiskLevel.CRITICAL)) == MaestroAction.ESCALATE


def test_contract_build_validate_recovery_and_evidence_validation():
    manager = AdaptiveOperatingContractManager()
    profile = _profile(RiskLevel.CRITICAL, audit=False)
    policy = _policy(mode=RuntimeMode.RESTRICTED_CRITICAL, human_gate_required=True)
    contract = manager.build_contract("wf", profile, policy, _tempo(15))

    assert MaestroAction.ARCHIVE not in contract.allowed_actions
    assert MaestroAction.ESCALATE in contract.human_gate_actions
    assert MaestroAction.PAUSE in contract.human_gate_actions
    assert contract.min_outcome_coverage == 0.98
    assert contract.critical_mode_locked is True

    bad_contract = manager.build_contract(
        "wf",
        profile,
        _policy(mode=RuntimeMode.RECOMMEND, human_gate_required=True),
        _tempo(15),
    )
    validation = manager.validate(
        bad_contract,
        quality_gate=_quality_gate(passed=False, metrics=_metrics(outcome_coverage=0.5)),
        runtime_invariants=_invariants(passed=False),
        pending_outcome_count=1,
        pending_approval_count=1,
        requested_action=MaestroAction.ARCHIVE,
        requested_patch=_patch(field=bad_contract.forbidden_patch_fields[0]),
        auto_apply_requested=True,
    )
    assert validation.passed is False
    assert "audit is disabled for this contract; adaptive evidence will be weaker" in validation.warnings
    assert any("outcome coverage" in item for item in validation.violations)
    assert "auto-apply requested while quality gate has not passed" in validation.violations
    assert "action archive is not allowed by operating contract" in validation.violations
    assert "patch auto-apply requires controlled adaptive runtime mode" in validation.violations
    assert "critical workflow contract must remain in restricted critical runtime mode" in validation.violations

    playbook = manager.build_recovery_playbook(
        "wf",
        findings=("retry rate increased", "informational only"),
        violations=("critical approval invariant",),
        handoff_repairs=(SimpleNamespace(edge_id="a->b", human_review_required=True, expected_effect="repair edge"),),
        pending_outcome_count=2,
        pending_approval_count=1,
    )
    assert [step.action for step in playbook.steps] == [
        "resolve_human_approvals",
        "collect_missing_outcomes",
        "repair_runtime_invariant",
        "execute_handoff_repair",
        "review_policy_finding",
    ]
    assert playbook.steps[2].requires_human_approval is True

    quiet = manager.build_recovery_playbook("wf")
    assert quiet.steps[0].action == "continue_observing"

    pack = _evidence_pack()
    pack_validation = manager.validate_evidence_pack(pack)
    assert pack_validation.valid is True
    assert "schema version adaptive-evidence-pack-1.8.0 is not the current 1.7.0 schema" in pack_validation.warnings

    mismatched = AdaptiveEvidencePack(
        workflow_id=pack.workflow_id,
        counts={**pack.counts, "checkpoints": 2},
        artifacts=pack.artifacts,
    )
    mismatch_validation = manager.validate_evidence_pack(mismatched)
    assert mismatch_validation.valid is False
    assert "checkpoints: count=2, artifact_len=0" in mismatch_validation.count_mismatches


def test_certification_covers_controlled_restricted_and_checksum_blocking():
    authority = AdaptiveCertificationAuthority()

    controlled_pack = _evidence_pack(runtime_mode=RuntimeMode.RECOMMEND, convergence_stable=True)
    controlled = authority.certify(controlled_pack)
    assert controlled.certified is True
    assert controlled.level == CertificationLevel.CONTROLLED_READY
    assert "schema version adaptive-evidence-pack-1.8.0 is not the current 1.7.0 schema" in controlled.warnings

    restricted = authority.certify(_evidence_pack(runtime_mode=RuntimeMode.RESTRICTED_CRITICAL))
    assert restricted.certified is True
    assert restricted.level == CertificationLevel.RESTRICTED_CRITICAL_READY

    blocked = authority.certify(controlled_pack, expected_checksum="0" * 64)
    assert blocked.certified is False
    assert blocked.level == CertificationLevel.BLOCKED
    assert "evidence pack failed integrity validation" in blocked.violations
    assert "evidence checksum does not match expected checksum" in blocked.warnings
    assert checksum(controlled_pack) == controlled.evidence_checksum


def test_replay_lab_comparison_history_and_counterfactual_branches():
    lab = ReplayLab()
    baseline = _policy(PolicyName.BALANCED, min_edge_psi=-0.05, max_retries=1)
    candidate = _policy(
        PolicyName.QUALITY_FIRST,
        min_edge_psi=0.1,
        max_retries=1,
        human_gate_required=True,
    )

    comparison = lab.compare(
        "wf",
        baseline,
        candidate,
        [DecisionOutcome("b1", "observe", "x", "x", decision_quality=0.5, cost_delta=0.1, latency_delta=0.1)],
        [DecisionOutcome("c1", "observe", "x", "x", decision_quality=0.7, cost_delta=0.12, latency_delta=0.0)],
    )
    assert comparison.recommendation == "prefer_candidate"
    assert comparison.quality_delta == 0.2

    events = [
        WorkflowHistoryEvent("wf", "checkpoint", action=MaestroAction.RETRY, quality_delta=0.01, cost_delta=0.1, latency_delta=0.1),
        WorkflowHistoryEvent("wf", "handoff_degradation", action=MaestroAction.RETRY, quality_delta=0.01, cost_delta=0.1, latency_delta=0.1),
        WorkflowHistoryEvent("wf", "weak_handoff", action=MaestroAction.REROUTE),
        WorkflowHistoryEvent("wf", "decision", action=MaestroAction.ESCALATE),
    ]
    replay = lab.replay_history("wf", baseline, candidate, events)
    assert replay.quality_delta > 0
    assert replay.latency_delta < 0.1

    scenarios = lab.counterfactual_scenarios("wf", baseline, events, candidate_policies=(baseline, candidate))
    assert [item.scenario for item in scenarios[:3]] == [
        "early_escalation",
        "remove_extra_retry",
        "insert_mediator",
    ]
    assert scenarios[0].recommendation == "prefer_scenario"
    assert scenarios[1].cost_delta < 0
    assert scenarios[2].quality_delta > 0
    assert scenarios[-1].scenario == f"policy_swap:{candidate.name.value}"


def test_ops_governor_allows_safe_transition_and_builds_serializable_evidence_pack(tmp_path):
    governor = AdaptiveOperationsGovernor()
    decision = governor.decide_mode_transition(
        workflow_id="wf-safe",
        current_mode=RuntimeMode.RECOMMEND,
        requested_mode=RuntimeMode.CONTROLLED_ADAPTIVE,
        profile=_profile(RiskLevel.LOW),
        quality_gate=_quality_gate(),
        runtime_invariants=_invariants(),
        metrics=_metrics(),
        pending_outcome_count=0,
        pending_approval_count=0,
    )
    assert decision.allowed is True
    assert decision.reason == "transition allowed"
    assert decision.violations == ()

    same_mode = governor.decide_mode_transition(
        workflow_id="wf-safe",
        current_mode=RuntimeMode.OBSERVE,
        requested_mode=RuntimeMode.OBSERVE,
        profile=_profile(RiskLevel.LOW),
        quality_gate=_quality_gate(),
        runtime_invariants=_invariants(),
        metrics=_metrics(),
        pending_outcome_count=0,
        pending_approval_count=0,
    )
    assert "requested runtime mode is already active" in same_mode.warnings

    demotion = governor.decide_mode_transition(
        workflow_id="wf-safe",
        current_mode=RuntimeMode.CONTROLLED_ADAPTIVE,
        requested_mode=RuntimeMode.OBSERVE,
        profile=_profile(RiskLevel.LOW),
        quality_gate=_quality_gate(),
        runtime_invariants=_invariants(),
        metrics=_metrics(),
        pending_outcome_count=0,
        pending_approval_count=0,
    )
    assert demotion.allowed is True
    assert "demotion to observe is safe and should be preferred after regressions" in demotion.warnings

    pack = governor.build_evidence_pack(
        workflow_id="wf-safe",
        profile=_profile(),
        policy=_policy(),
        tempo=_tempo(),
        metrics=_metrics(),
        quality_gate=_quality_gate(),
        runtime_invariants=_invariants(),
        checkpoints=({"kind": CheckpointKind.MILESTONE, "score": 1},),
        drift_alerts=({"severity": RiskLevel.HIGH},),
        handoff_suggestions=("handoff",),
        policy_critiques=("critique",),
        policy_patches=(_patch(),),
        approvals=("approval",),
        history=("history",),
        replay_results=("replay",),
        transition_decision=decision,
        operating_contract={"mode": RuntimeMode.RECOMMEND},
        contract_validation={"passed": True},
        convergence_report={"stable": True},
        recovery_playbook={"steps": []},
        evidence_pack_validation={"valid": True},
        runtime_commands=("command",),
        auto_outcome_reports=("outcome",),
        checkpoint_coalescing=("coalescing",),
        runtime_deduplication=("dedupe",),
        efficiency_reports=("efficiency",),
        checkpoint_backpressure=("backpressure",),
        runtime_batches=("batch",),
        outcome_sweep_plans=("sweep",),
        workload_budget_decisions=("budget",),
        runtime_conflicts=("conflict",),
        evidence_digests=("digest",),
        runtime_throttles=("throttle",),
        evidence_deltas=("delta",),
        encrypted_reports=("encrypted",),
        encrypted_report_indexes=("index",),
        ui_snapshots=("ui",),
    )
    assert pack.counts["checkpoints"] == 1
    assert pack.counts["runtime_commands"] == 1
    assert pack.counts["ui_snapshots"] == 1
    assert pack.artifacts["profile"]["risk"] == RiskLevel.LOW
    assert pack.artifacts["transition_decision"]["allowed"] is True

    output = governor.write_evidence_pack(pack, tmp_path / "nested" / "evidence.json")
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert '"workflow_id": "wf-safe"' in text
    assert '"runtime_commands": 1' in text


def test_ops_governor_critical_transition_is_explicitly_blocked():
    governor = AdaptiveOperationsGovernor()
    decision = governor.decide_mode_transition(
        workflow_id="wf-critical",
        current_mode=RuntimeMode.RESTRICTED_CRITICAL,
        requested_mode=RuntimeMode.RECOMMEND,
        profile=_profile(RiskLevel.CRITICAL),
        quality_gate=_quality_gate(),
        runtime_invariants=_invariants(),
        metrics=_metrics(),
        pending_outcome_count=0,
        pending_approval_count=0,
    )
    assert decision.required_human_approval is True
    assert "critical workflows must remain in restricted critical mode" in decision.violations
    assert decision.reason == "transition blocked by safety evidence"


def test_checkpoint_report_covers_agents_handoffs_risks_and_remaining_actions():
    scheduler = CheckpointScheduler()
    profile = _profile(RiskLevel.HIGH)
    policy = _policy()

    step_a = WorkflowStep("s1", "x", "do", preferred_agent_id="a")
    step_b = WorkflowStep("s2", "x", "do", preferred_agent_id="b")
    plan = WorkflowPlan(workflow_id="wf", goal="test", steps=(step_a, step_b))
    workflow = WorkflowRecord(plan=plan, state=WorkflowState.DEGRADED, psi=-0.2, previous_psi=0.1)
    workflow.steps["s1"] = StepRecord(step=step_a, state=StepState.FAILED, assigned_agent_id="a")
    workflow.steps["s2"] = StepRecord(step=step_b, state=StepState.RUNNING, assigned_agent_id="b")

    registry = {
        "a": SimpleNamespace(state=AgentState.TRANSITIONAL, psi=-0.1, previous_psi=0.1, failure_streak=2),
        "b": SimpleNamespace(state=AgentState.ACTIVE, psi=0.5, previous_psi=0.48, failure_streak=0),
    }
    handoffs = {
        "a->b": SimpleNamespace(source_agent_id="a", target_agent_id="b", state=AgentState.QUARANTINED, psi=-0.2, previous_psi=0.0, observations=3),
        "x->y": SimpleNamespace(source_agent_id="x", target_agent_id="y", state=AgentState.ACTIVE, psi=0.5, previous_psi=0.5, observations=1),
    }
    kernel = SimpleNamespace(get_workflow=lambda workflow_id: workflow, registry=registry, handoffs=handoffs)

    report = scheduler.build_report(kernel, "wf", profile, policy, CheckpointKind.EVENT_BASED, now=123.0)
    assert report.checkpoint_number == 1
    assert report.created_at == 123.0
    assert report.workflow_status["failed_steps"] == 1
    assert report.workflow_status["running_steps"] == 1
    assert report.agent_findings["a"]["status"] == "degraded"
    assert report.agent_findings["b"]["status"] == "stable"
    assert report.handoff_findings["a->b"]["status"] == "weak"
    assert "x->y" not in report.handoff_findings
    assert any(item.startswith("failed_steps:") for item in report.risks)
    assert any(item.startswith("degraded_agents:") for item in report.risks)
    assert any(item.startswith("weak_handoffs:") for item in report.risks)
    assert "profile_risk:high" in report.risks
    assert "workflow_state:degraded" in report.risks
    assert report.recommended_action == MaestroAction.REROUTE
    assert 0.0 <= report.confidence < 0.85

    paused = WorkflowRecord(plan=plan, state=WorkflowState.PAUSED)
    assert scheduler._recommended_action(paused, [], _profile()) == MaestroAction.PAUSE
    running = WorkflowRecord(plan=plan, state=WorkflowState.RUNNING)
    assert scheduler._recommended_action(running, [], _profile()) == MaestroAction.OBSERVE

    no_interval = _policy()
    object.__setattr__(no_interval, "checkpoint_interval_minutes", None)
    assert scheduler._checkpoint_kind("new", _profile(), no_interval, None, False, False, 10.0) is None

    short_profile = TaskProfile(
        size=TaskSize.SMALL,
        duration=TaskDuration.SHORT,
        risk=RiskLevel.LOW,
        ambiguity=AmbiguityLevel.LOW,
        agent_count=AgentCountBand.SINGLE,
    )
    assert scheduler._checkpoint_kind("fresh", short_profile, policy, None, False, False, 10.0) == CheckpointKind.MILESTONE


def test_contract_happy_path_human_gate_and_schema_edge_cases():
    manager = AdaptiveOperatingContractManager()
    contract = manager.build_contract("wf", _profile(), _policy(mode=RuntimeMode.CONTROLLED_ADAPTIVE), _tempo())
    valid = manager.validate(
        contract,
        quality_gate=_quality_gate(metrics=_metrics(outcome_coverage=1.0)),
        runtime_invariants=_invariants(),
        requested_action=MaestroAction.OBSERVE,
        requested_patch=_patch(),
        auto_apply_requested=True,
    )
    assert valid.passed is True
    assert valid.violations == ()

    gated = manager.validate(
        contract,
        requested_action=MaestroAction.REROUTE,
        auto_apply_requested=True,
    )
    assert gated.passed is False
    assert "action reroute requires human approval" in gated.violations

    minimal = AdaptiveEvidencePack(
        workflow_id="wf",
        counts={},
        artifacts={},
        schema_version="legacy-pack",
    )
    invalid = manager.validate_evidence_pack(minimal)
    assert invalid.valid is False
    assert "profile" in invalid.missing_artifacts
    assert "unknown evidence pack schema namespace" in invalid.warnings
    assert "schema version legacy-pack is not the current 1.7.0 schema" in invalid.warnings

    current = AdaptiveEvidencePack(
        workflow_id="wf",
        counts={},
        artifacts={name: [] if name in {"checkpoints", "policy_patches", "history"} else {} for name in manager.REQUIRED_EVIDENCE_ARTIFACTS},
        schema_version="adaptive-evidence-pack-1.7.0",
    )
    current_validation = manager.validate_evidence_pack(current)
    assert current_validation.warnings == ()


def test_certification_recommend_ready_and_blocked_evidence_paths():
    authority = AdaptiveCertificationAuthority()
    recommend_pack = _evidence_pack(convergence_stable=False)
    recommend = authority.certify(recommend_pack)
    assert recommend.certified is True
    assert recommend.level == CertificationLevel.RECOMMEND_READY
    assert "adaptive convergence window is not stable yet; keep expansion cautious" in recommend.warnings

    blocked_pack = _evidence_pack(
        q_passed=False,
        invariants_passed=False,
        contract_passed=False,
        convergence_stable=False,
        pending_outcomes=2,
        pending_approvals=1,
    )
    blocked = authority.certify(blocked_pack)
    assert blocked.level == CertificationLevel.BLOCKED
    assert "quality gate has not passed" in blocked.violations
    assert "runtime invariants have not passed" in blocked.violations
    assert "operating contract validation has not passed" in blocked.violations
    assert "2 pending outcome(s) remain unresolved" in blocked.violations
    assert "1 pending approval request(s) remain unresolved" in blocked.violations


def test_replay_empty_inputs_no_escalation_bonus_and_keep_baseline_branches():
    lab = ReplayLab()
    baseline = _policy(PolicyName.BALANCED, min_edge_psi=0.2, max_retries=3)
    candidate = _policy(PolicyName.COST_SAVING, min_edge_psi=-0.2, max_retries=5, human_gate_required=True)

    empty = lab.compare("wf", baseline, candidate, [], [])
    assert empty.quality_delta == 0.0
    assert empty.cost_delta == 0.0
    assert empty.recommendation == "keep_baseline"

    events = [WorkflowHistoryEvent("wf", "decision", action=MaestroAction.OBSERVE)]
    replay = lab.replay_history("wf", baseline, candidate, events)
    assert replay.quality_delta == 0.01
    assert replay.recommendation == "keep_baseline"

    scenarios = lab.counterfactual_scenarios("wf", baseline, [], candidate_policies=(candidate,))
    assert scenarios[0].recommendation == "keep_baseline"
    assert scenarios[0].sample_size == 1
    assert scenarios[1].recommendation == "keep_baseline"
    assert scenarios[2].recommendation == "keep_baseline"
    assert scenarios[-1].recommendation == "keep_baseline"

    many = [WorkflowHistoryEvent("wf", "checkpoint") for _ in range(20)]
    capped = lab._early_escalation("wf", many)
    assert capped.quality_delta == 0.18
    assert capped.latency_delta == -0.12
    assert capped.confidence == 0.9

