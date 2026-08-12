from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit
from processual_kernel.adaptive_types import RuntimeMode
from processual_kernel.audit import AuditEventType
from processual_kernel.types import KernelPolicy, MaestroAction


def make_toolkit(*, mode: RuntimeMode = RuntimeMode.RECOMMEND) -> tuple[AdaptiveGovernanceToolkit, SimpleNamespace]:
    kernel = SimpleNamespace(policy=KernelPolicy(), _audit=Mock(), get_workflow=Mock(return_value=object()))
    return AdaptiveGovernanceToolkit(kernel, mode=mode), kernel


def test_init_audit_and_persist_helpers() -> None:
    toolkit, kernel = make_toolkit()
    assert toolkit.store is None
    assert toolkit._profiles == {}
    assert toolkit._operating_contracts == {}
    assert toolkit._contract_validations == {}
    assert toolkit._convergence_reports == {}

    toolkit._audit_adaptive(AuditEventType.RUNTIME_INVARIANT, "wf-1", {"passed": True})
    kernel._audit.assert_called_once_with({
        "event_type": AuditEventType.RUNTIME_INVARIANT.value,
        "subject_id": "wf-1",
        "passed": True,
    })

    toolkit.kernel = SimpleNamespace(policy=KernelPolicy(), _audit=None)
    toolkit._audit_adaptive(AuditEventType.RUNTIME_INVARIANT, "wf-2", {"passed": False})

    store = Mock()
    toolkit.store = store
    artifact = object()
    toolkit._persist("kind", artifact)
    store.append.assert_called_once_with("kind", artifact)
    toolkit.store = None
    toolkit._persist("kind", artifact)


def test_record_history_event_audits_and_persists() -> None:
    toolkit, _ = make_toolkit()
    audit = Mock()
    persist = Mock()
    toolkit._audit_adaptive = audit
    toolkit._persist = persist
    event = SimpleNamespace(workflow_id="wf-1", event_type="step_completed", action=MaestroAction.OBSERVE)

    toolkit._record_history_event(event)
    args = audit.call_args.args
    assert args[0] == AuditEventType.WORKFLOW_HISTORY_EVENT
    assert args[1] == "wf-1"
    assert args[2]["event_type_name"] == "step_completed"
    assert args[2]["action"] == MaestroAction.OBSERVE.value
    assert args[2]["payload"] is event
    persist.assert_called_once_with("workflow_history", event)

    event.action = None
    toolkit._record_history_event(event)
    assert audit.call_args.args[2]["action"] is None


def test_human_approval_request_pending_and_approve() -> None:
    toolkit, kernel = make_toolkit()
    toolkit.safety_guard = Mock()
    audit = Mock()
    persist = Mock()
    toolkit._audit_adaptive = audit
    toolkit._persist = persist
    request = SimpleNamespace(
        request_id="req-1", workflow_id="wf-1", action="pause", reason="risk",
        policy_version="unversioned", approved=False,
    )
    toolkit.safety_guard.request_approval.return_value = request

    assert toolkit.request_human_approval("wf-1", "pause", "risk", ticket="INC-1") is request
    toolkit.safety_guard.request_approval.assert_called_once_with(
        workflow_id="wf-1", action="pause", reason="risk",
        policy_version=getattr(kernel.policy, "policy_version", "unversioned"), ticket="INC-1",
    )
    assert audit.call_args.args[0] == AuditEventType.HUMAN_APPROVAL_REQUEST
    assert audit.call_args.args[2]["request_id"] == "req-1"
    persist.assert_called_once_with("human_approval_requests", request)

    toolkit.safety_guard.pending.return_value = (request,)
    assert toolkit.pending_approval_requests("wf-1") == (request,)
    toolkit.safety_guard.pending.assert_called_once_with(workflow_id="wf-1")

    approved = SimpleNamespace(
        request_id="req-1", workflow_id="wf-1", action="pause", reason="risk",
        policy_version="unversioned", approved=True,
    )
    toolkit.safety_guard.approve.return_value = approved
    assert toolkit.approve_human_request("req-1") is approved
    toolkit.safety_guard.approve.assert_called_once_with("req-1")
    assert audit.call_args.args[2]["approved"] is True
    assert persist.call_args.args == ("human_approval_requests", approved)


def test_runtime_invariant_report_covers_critical_and_controlled_warnings() -> None:
    toolkit, _ = make_toolkit(mode=RuntimeMode.CONTROLLED_ADAPTIVE)
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit.pending_outcomes = Mock(return_value=(object(),))
    toolkit.safety_guard = Mock()
    toolkit.safety_guard.requires_human_gate.return_value = False
    critical_profile = SimpleNamespace(risk=SimpleNamespace(value="critical"))
    observe_policy = SimpleNamespace(runtime_mode=RuntimeMode.OBSERVE)

    report = toolkit.runtime_invariant_report(
        "wf-1", profile=critical_profile, policy=observe_policy, auto_apply_requested=True
    )
    assert report.passed is False
    assert "high/critical workflow is not protected by a human gate" in report.violations
    assert "critical workflow must use restricted critical runtime mode" in report.violations
    assert "auto-apply requested under observe/restricted policy" in report.violations
    assert report.warnings == (
        "controlled mode has pending decision outcomes; keep calibration conservative",
    )
    assert toolkit._audit_adaptive.call_args.args[2]["violation_count"] == 3
    toolkit._persist.assert_called_once_with("runtime_invariants", report)

    toolkit.safety_guard.requires_human_gate.return_value = True
    toolkit.pending_outcomes.return_value = ()
    high_profile = SimpleNamespace(risk=SimpleNamespace(value="high"))
    controlled_policy = SimpleNamespace(runtime_mode=RuntimeMode.CONTROLLED_ADAPTIVE)
    gated = toolkit.runtime_invariant_report(
        "wf-2", profile=high_profile, policy=controlled_policy, auto_apply_requested=True
    )
    assert gated.violations == ("auto-apply requested while a human gate is required",)
    assert gated.warnings == ()


def test_runtime_invariant_report_resolves_profile_and_policy_fallbacks() -> None:
    toolkit, kernel = make_toolkit()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit.pending_outcomes = Mock(return_value=())
    toolkit.safety_guard = Mock()
    toolkit.safety_guard.requires_human_gate.return_value = False
    profile = SimpleNamespace(risk=SimpleNamespace(value="low"))
    policy = SimpleNamespace(runtime_mode=RuntimeMode.RECOMMEND)
    toolkit.profile_task = Mock(return_value=profile)
    toolkit.select_policy = Mock(return_value=policy)

    report = toolkit.runtime_invariant_report("wf-1")
    assert report.passed is True
    assert report.violations == ()
    kernel.get_workflow.assert_called_once_with("wf-1")
    toolkit.select_policy.assert_called_once_with(profile, workflow_id="wf-1")


def test_operating_contract_builds_caches_audits_and_persists() -> None:
    toolkit, kernel = make_toolkit()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    profile = SimpleNamespace(risk=SimpleNamespace(value="low"))
    policy = SimpleNamespace(runtime_mode=RuntimeMode.RECOMMEND)
    tempo = object()
    toolkit.profile_task = Mock(return_value=profile)
    toolkit.select_policy = Mock(return_value=policy)
    toolkit.plan_tempo = Mock(return_value=tempo)
    contract = SimpleNamespace(
        runtime_mode=RuntimeMode.RECOMMEND, policy_version="p1",
        human_gate_actions=(MaestroAction.PAUSE,), forbidden_patch_fields=("dt", "min_psi"),
    )
    toolkit.contracts = Mock()
    toolkit.contracts.build_contract.return_value = contract

    assert toolkit.operating_contract("wf-1") is contract
    assert toolkit._operating_contracts["wf-1"] is contract
    kernel.get_workflow.assert_called_once_with("wf-1")
    toolkit.contracts.build_contract.assert_called_once_with("wf-1", profile, policy, tempo)
    payload = toolkit._audit_adaptive.call_args.args[2]
    assert payload["runtime_mode"] == RuntimeMode.RECOMMEND.value
    assert payload["human_gate_action_count"] == 1
    assert payload["forbidden_patch_field_count"] == 2
    toolkit._persist.assert_called_once_with("operating_contracts", contract)


def test_validate_operating_contract_passes_pending_counts_and_requested_inputs() -> None:
    toolkit, _ = make_toolkit()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit.pending_outcomes = Mock(return_value=(1, 2))
    toolkit.pending_approval_requests = Mock(return_value=(3,))
    toolkit.contracts = Mock()
    contract = object()
    quality_gate = object()
    invariants = object()
    patch = object()
    validation = SimpleNamespace(passed=False, violations=("v1", "v2"), warnings=("w1",))
    toolkit.contracts.validate.return_value = validation

    assert toolkit.validate_operating_contract(
        "wf-1", contract=contract, quality_gate=quality_gate, runtime_invariants=invariants,
        requested_action=MaestroAction.PAUSE, requested_patch=patch, auto_apply_requested=True,
    ) is validation
    assert toolkit._contract_validations["wf-1"] == [validation]
    toolkit.contracts.validate.assert_called_once_with(
        contract, quality_gate=quality_gate, runtime_invariants=invariants,
        pending_outcome_count=2, pending_approval_count=1,
        requested_action=MaestroAction.PAUSE, requested_patch=patch, auto_apply_requested=True,
    )
    payload = toolkit._audit_adaptive.call_args.args[2]
    assert payload["violation_count"] == 2
    assert payload["warning_count"] == 1
    toolkit._persist.assert_called_once_with("operating_contract_validations", validation)


def test_validate_operating_contract_resolves_default_artifacts() -> None:
    toolkit, _ = make_toolkit()
    contract = object()
    quality_gate = object()
    invariants = object()
    validation = SimpleNamespace(passed=True, violations=(), warnings=())
    toolkit.operating_contract = Mock(return_value=contract)
    toolkit.quality_gate_report = Mock(return_value=quality_gate)
    toolkit.runtime_invariant_report = Mock(return_value=invariants)
    toolkit.pending_outcomes = Mock(return_value=())
    toolkit.pending_approval_requests = Mock(return_value=())
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit.contracts = Mock()
    toolkit.contracts.validate.return_value = validation

    assert toolkit.validate_operating_contract("wf-1") is validation
    toolkit.operating_contract.assert_called_once_with("wf-1")
    toolkit.quality_gate_report.assert_called_once_with("wf-1")
    toolkit.runtime_invariant_report.assert_called_once_with("wf-1")


def test_convergence_report_records_audits_and_persists() -> None:
    toolkit, _ = make_toolkit()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit.convergence_monitor = Mock()
    report = SimpleNamespace(stable=True, window_size=5, recommendation="hold")
    toolkit.convergence_monitor.evaluate.return_value = report

    assert toolkit.convergence_report("wf-1") is report
    assert toolkit._convergence_reports["wf-1"] == [report]
    toolkit.convergence_monitor.evaluate.assert_called_once_with("wf-1")
    payload = toolkit._audit_adaptive.call_args.args[2]
    assert payload["stable"] is True
    assert payload["window_size"] == 5
    assert payload["recommendation"] == "hold"
    toolkit._persist.assert_called_once_with("adaptive_convergence", report)
