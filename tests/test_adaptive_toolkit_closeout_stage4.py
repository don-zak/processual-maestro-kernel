from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit
from processual_kernel.adaptive_types import RuntimeMode
from processual_kernel.types import MaestroAction


def make_toolkit() -> AdaptiveGovernanceToolkit:
    toolkit = object.__new__(AdaptiveGovernanceToolkit)
    toolkit.kernel = Mock()
    toolkit.store = None
    toolkit.safety_guard = Mock()
    toolkit.contracts = Mock()
    toolkit.convergence_monitor = Mock()
    toolkit._profiles = {}
    toolkit._policies = {}
    toolkit._tempo_plans = {}
    toolkit._operating_contracts = {}
    toolkit._contract_validations = {}
    toolkit._convergence_reports = {}
    toolkit._recovery_playbooks = {}
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit.pending_outcomes = Mock(return_value=())
    toolkit.pending_approval_requests = Mock(return_value=())
    toolkit.profile_task = Mock()
    toolkit.select_policy = Mock()
    toolkit.plan_tempo = Mock()
    toolkit.quality_gate_report = Mock()
    toolkit.review_policy = Mock()
    toolkit.mode = RuntimeMode.RECOMMEND
    return toolkit


def test_human_approval_lifecycle_delegates_audits_and_persists() -> None:
    toolkit = make_toolkit()
    toolkit.kernel.policy = SimpleNamespace(policy_version="v-current")
    pending = SimpleNamespace(
        request_id="req-1",
        workflow_id="wf-1",
        action="pause",
        reason="risk",
        policy_version="v-current",
        approved=False,
    )
    approved = SimpleNamespace(**{**pending.__dict__, "approved": True})
    toolkit.safety_guard.request_approval.return_value = pending
    toolkit.safety_guard.pending.return_value = (pending,)
    toolkit.safety_guard.approve.return_value = approved

    result = toolkit.request_human_approval(
        "wf-1", MaestroAction.PAUSE, "risk", owner="ops"
    )
    assert result is pending
    toolkit.safety_guard.request_approval.assert_called_once_with(
        workflow_id="wf-1",
        action=MaestroAction.PAUSE,
        reason="risk",
        policy_version="v-current",
        owner="ops",
    )
    assert toolkit.safety_guard.pending(workflow_id="wf-1") == (pending,)

    result = toolkit.approve_human_request("req-1")
    assert result is approved
    toolkit.safety_guard.approve.assert_called_once_with("req-1")
    assert toolkit._persist.call_count == 2
    assert toolkit._audit_adaptive.call_count == 2


def test_runtime_invariants_report_all_safety_violations_and_warning() -> None:
    toolkit = make_toolkit()
    profile = SimpleNamespace(risk=SimpleNamespace(value="critical"))
    policy = SimpleNamespace(runtime_mode=RuntimeMode.OBSERVE)
    toolkit.safety_guard.requires_human_gate.return_value = False
    toolkit.pending_outcomes.return_value = ("pending",)
    toolkit.mode = RuntimeMode.CONTROLLED_ADAPTIVE

    report = toolkit.runtime_invariant_report(
        "wf-1", profile=profile, policy=policy, auto_apply_requested=True
    )

    assert report.passed is False
    assert "high/critical workflow is not protected by a human gate" in report.violations
    assert "critical workflow must use restricted critical runtime mode" in report.violations
    assert "auto-apply requested under observe/restricted policy" in report.violations
    assert report.warnings == (
        "controlled mode has pending decision outcomes; keep calibration conservative",
    )
    toolkit._persist.assert_called_once_with("runtime_invariants", report)


def test_runtime_invariants_resolve_missing_profile_and_policy() -> None:
    toolkit = make_toolkit()
    workflow = SimpleNamespace(workflow_id="wf-2")
    profile = SimpleNamespace(risk=SimpleNamespace(value="medium"))
    policy = SimpleNamespace(runtime_mode=RuntimeMode.RECOMMEND)
    toolkit.kernel.get_workflow.return_value = workflow
    toolkit.profile_task.return_value = profile
    toolkit.select_policy.return_value = policy
    toolkit.safety_guard.requires_human_gate.return_value = False

    report = toolkit.runtime_invariant_report("wf-2")

    assert report.passed is True
    toolkit.profile_task.assert_called_once_with(workflow)
    toolkit.select_policy.assert_called_once_with(profile, workflow_id="wf-2")


def test_operating_contract_resolves_inputs_records_and_persists() -> None:
    toolkit = make_toolkit()
    workflow = SimpleNamespace(workflow_id="wf-3")
    profile = SimpleNamespace(risk=SimpleNamespace(value="medium"))
    policy = SimpleNamespace(runtime_mode=RuntimeMode.RECOMMEND)
    tempo = SimpleNamespace(name="tempo")
    contract = SimpleNamespace(
        runtime_mode=RuntimeMode.RECOMMEND,
        policy_version="v2",
        human_gate_actions=("escalate",),
        forbidden_patch_fields=("core",),
    )
    toolkit.kernel.get_workflow.return_value = workflow
    toolkit.profile_task.return_value = profile
    toolkit.select_policy.return_value = policy
    toolkit.plan_tempo.return_value = tempo
    toolkit.contracts.build_contract.return_value = contract

    result = toolkit.operating_contract("wf-3")

    assert result is contract
    toolkit.contracts.build_contract.assert_called_once_with(
        "wf-3", profile, policy, tempo
    )
    assert toolkit._operating_contracts["wf-3"] is contract
    toolkit._persist.assert_called_once_with("operating_contracts", contract)


def test_validate_operating_contract_forwards_counts_and_request() -> None:
    toolkit = make_toolkit()
    contract = SimpleNamespace(name="contract")
    gate = SimpleNamespace(name="gate")
    invariants = SimpleNamespace(name="invariants")
    validation = SimpleNamespace(passed=False, violations=("blocked",), warnings=("warn",))
    patch = SimpleNamespace(field="threshold")
    toolkit.contracts.validate.return_value = validation
    toolkit.pending_outcomes.return_value = (1, 2)
    toolkit.pending_approval_requests.return_value = (3,)

    result = toolkit.validate_operating_contract(
        "wf-4",
        contract=contract,
        quality_gate=gate,
        runtime_invariants=invariants,
        requested_action=MaestroAction.PAUSE,
        requested_patch=patch,
        auto_apply_requested=True,
    )

    assert result is validation
    toolkit.contracts.validate.assert_called_once_with(
        contract,
        quality_gate=gate,
        runtime_invariants=invariants,
        pending_outcome_count=2,
        pending_approval_count=1,
        requested_action=MaestroAction.PAUSE,
        requested_patch=patch,
        auto_apply_requested=True,
    )
    assert toolkit._contract_validations["wf-4"] == [validation]
    toolkit._persist.assert_called_once_with("operating_contract_validations", validation)


def test_convergence_report_tracks_history_and_recovery_playbook_inputs() -> None:
    toolkit = make_toolkit()
    convergence = SimpleNamespace(
        stable=True,
        window_size=5,
        recommendation="hold",
    )
    toolkit.convergence_monitor.evaluate.return_value = convergence

    assert toolkit.convergence_report("wf-5") is convergence
    assert toolkit._convergence_reports["wf-5"] == [convergence]

    critique = SimpleNamespace(findings=("finding",))
    invariants = SimpleNamespace(violations=("violation",))
    repair = SimpleNamespace(edge_id="edge-1")
    playbook = SimpleNamespace(
        workflow_id="wf-5",
        steps=("recover",),
        confidence=0.9,
    )
    toolkit.pending_outcomes.return_value = ("pending",)
    toolkit.pending_approval_requests.return_value = ("approval", "approval-2")
    toolkit.contracts.build_recovery_playbook.return_value = playbook

    result = toolkit.build_recovery_playbook(
        "wf-5",
        critique=critique,
        runtime_invariants=invariants,
        handoff_repairs=(repair,),
    )

    assert result is playbook
    toolkit.contracts.build_recovery_playbook.assert_called_once_with(
        workflow_id="wf-5",
        findings=("finding",),
        violations=("violation",),
        handoff_repairs=(repair,),
        pending_outcome_count=1,
        pending_approval_count=2,
    )
    assert toolkit._recovery_playbooks["wf-5"] is playbook
