from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit
from processual_kernel.types import KernelPolicy, MaestroAction


def make_toolkit() -> tuple[AdaptiveGovernanceToolkit, SimpleNamespace]:
    kernel = SimpleNamespace(
        policy=KernelPolicy(),
        governor=SimpleNamespace(policy=None),
        _audit=Mock(),
        get_workflow=Mock(return_value=object()),
        intervene=Mock(),
    )
    return AdaptiveGovernanceToolkit(kernel), kernel


def test_build_recovery_playbook_resolves_defaults_and_records() -> None:
    toolkit, _ = make_toolkit()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    critique = SimpleNamespace(findings=("slow handoff",))
    invariants = SimpleNamespace(violations=("gate missing",))
    repairs = (object(),)
    toolkit.review_policy = Mock(return_value=critique)
    toolkit.runtime_invariant_report = Mock(return_value=invariants)
    toolkit.pending_outcomes = Mock(return_value=(1, 2))
    toolkit.pending_approval_requests = Mock(return_value=(3,))
    toolkit.contracts = Mock()
    playbook = SimpleNamespace(steps=("pause", "review"), confidence=0.8)
    toolkit.contracts.build_recovery_playbook.return_value = playbook

    assert toolkit.build_recovery_playbook("wf-1", handoff_repairs=repairs) is playbook
    assert toolkit._recovery_playbooks["wf-1"] is playbook
    toolkit.review_policy.assert_called_once_with("wf-1")
    toolkit.runtime_invariant_report.assert_called_once_with("wf-1")
    toolkit.contracts.build_recovery_playbook.assert_called_once_with(
        workflow_id="wf-1",
        findings=critique.findings,
        violations=invariants.violations,
        handoff_repairs=repairs,
        pending_outcome_count=2,
        pending_approval_count=1,
    )
    payload = toolkit._audit_adaptive.call_args.args[2]
    assert payload["step_count"] == 2
    assert payload["confidence"] == 0.8
    toolkit._persist.assert_called_once_with("recovery_playbooks", playbook)


def test_validate_adaptive_evidence_pack_records_validation() -> None:
    toolkit, _ = make_toolkit()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit.contracts = Mock()
    pack = SimpleNamespace(workflow_id="wf-1")
    result = SimpleNamespace(
        schema_version="1.7.0",
        valid=False,
        missing_artifacts=("quality_gate",),
        count_mismatches=("events", "decisions"),
    )
    toolkit.contracts.validate_evidence_pack.return_value = result

    assert toolkit.validate_adaptive_evidence_pack(pack) is result
    assert toolkit._evidence_pack_validations["wf-1"] == [result]
    toolkit.contracts.validate_evidence_pack.assert_called_once_with(pack)
    payload = toolkit._audit_adaptive.call_args.args[2]
    assert payload["schema_version"] == "1.7.0"
    assert payload["valid"] is False
    assert payload["missing_artifact_count"] == 1
    assert payload["count_mismatch_count"] == 2
    toolkit._persist.assert_called_once_with("evidence_pack_validations", result)


def test_validate_adaptive_integrity_audits_and_persists() -> None:
    toolkit, _ = make_toolkit()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit.certifier = Mock()
    pack = SimpleNamespace(workflow_id="wf-1")
    report = SimpleNamespace(schema_version="1.7.0", valid=True, checksum="abc", artifact_count=9)
    toolkit.certifier.integrity_report.return_value = report

    assert toolkit.validate_adaptive_integrity(pack, expected_checksum="abc") is report
    toolkit.certifier.integrity_report.assert_called_once_with(pack, expected_checksum="abc")
    payload = toolkit._audit_adaptive.call_args.args[2]
    assert payload["valid"] is True
    assert payload["checksum"] == "abc"
    assert payload["artifact_count"] == 9
    toolkit._persist.assert_called_once_with("adaptive_integrity", report)


def test_certify_adaptive_readiness_uses_existing_pack_and_default_builder() -> None:
    toolkit, _ = make_toolkit()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit.certifier = Mock()
    report = SimpleNamespace(
        level=SimpleNamespace(value="ready"),
        certified=True,
        violations=(),
        evidence_checksum="sum-1",
    )
    toolkit.certifier.certify.return_value = report
    pack = object()

    assert toolkit.certify_adaptive_readiness("wf-1", pack=pack, expected_checksum="sum-1") is report
    toolkit.certifier.certify.assert_called_once_with(pack, expected_checksum="sum-1")
    payload = toolkit._audit_adaptive.call_args.args[2]
    assert payload["level"] == "ready"
    assert payload["certified"] is True
    assert payload["violation_count"] == 0
    toolkit._persist.assert_called_once_with("adaptive_certifications", report)

    toolkit.certifier.certify.reset_mock()
    toolkit.build_adaptive_evidence_pack = Mock(return_value=pack)
    toolkit.certify_adaptive_readiness("wf-2")
    toolkit.build_adaptive_evidence_pack.assert_called_once_with("wf-2")
    toolkit.certifier.certify.assert_called_once_with(pack, expected_checksum=None)


def _configure_authorization_dependencies(toolkit: AdaptiveGovernanceToolkit) -> tuple[object, object, object, object]:
    profile = object()
    policy = SimpleNamespace(policy_version="p1")
    tempo = object()
    contract = SimpleNamespace(human_gate_actions=())
    toolkit.profile_task = Mock(return_value=profile)
    toolkit.select_policy = Mock(return_value=policy)
    toolkit.plan_tempo = Mock(return_value=tempo)
    toolkit.operating_contract = Mock(return_value=contract)
    toolkit.quality_gate_report = Mock(return_value=object())
    toolkit.runtime_invariant_report = Mock(return_value=object())
    return profile, policy, tempo, contract


def test_authorize_adaptive_action_auto_executes_authorized_action() -> None:
    toolkit, kernel = make_toolkit()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    profile, policy, tempo, contract = _configure_authorization_dependencies(toolkit)
    validation = SimpleNamespace(passed=True, violations=(), warnings=())
    toolkit.validate_operating_contract = Mock(return_value=validation)

    report = toolkit.authorize_adaptive_action(
        "wf-1",
        "pause",
        reason="operator policy",
        auto_execute=True,
        subject="step-1",
        metadata={"ticket": "INC-1"},
    )

    assert report.action == MaestroAction.PAUSE
    assert report.authorized is True
    assert report.requires_human_approval is False
    assert report.executed is True
    toolkit.select_policy.assert_called_once_with(profile, workflow_id="wf-1")
    toolkit.plan_tempo.assert_called_once_with(profile, policy, workflow_id="wf-1")
    toolkit.operating_contract.assert_called_once_with("wf-1", profile=profile, policy=policy, tempo=tempo)
    toolkit.validate_operating_contract.assert_called_once()
    kernel.intervene.assert_called_once_with(
        "wf-1", MaestroAction.PAUSE, "step-1", "operator policy", {"ticket": "INC-1"}
    )
    payload = toolkit._audit_adaptive.call_args.args[2]
    assert payload["authorized"] is True
    assert payload["executed"] is True
    toolkit._persist.assert_called_once_with("action_authorizations", report)


def test_authorize_adaptive_action_requests_human_gate_and_does_not_execute() -> None:
    toolkit, kernel = make_toolkit()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    profile, policy, tempo, _ = _configure_authorization_dependencies(toolkit)
    gated_contract = SimpleNamespace(human_gate_actions=(MaestroAction.PAUSE,))
    toolkit.operating_contract.return_value = gated_contract
    validation = SimpleNamespace(passed=True, violations=(), warnings=("approval required",))
    toolkit.validate_operating_contract = Mock(return_value=validation)
    request = SimpleNamespace(request_id="req-1")
    toolkit.request_human_approval = Mock(return_value=request)

    report = toolkit.authorize_adaptive_action("wf-1", MaestroAction.PAUSE, auto_execute=True)

    assert report.authorized is False
    assert report.requires_human_approval is True
    assert report.request_id == "req-1"
    assert report.executed is False
    toolkit.request_human_approval.assert_called_once_with(
        "wf-1",
        MaestroAction.PAUSE,
        "adaptive action authorization; action requires operating-contract approval",
        policy_version=policy.policy_version,
    )
    kernel.intervene.assert_not_called()
    toolkit.operating_contract.assert_called_once_with("wf-1", profile=profile, policy=policy, tempo=tempo)


def test_authorize_adaptive_action_blocked_validation_preserves_details() -> None:
    toolkit, kernel = make_toolkit()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    _configure_authorization_dependencies(toolkit)
    validation = SimpleNamespace(passed=False, violations=("contract violation",), warnings=("review",))
    toolkit.validate_operating_contract = Mock(return_value=validation)

    report = toolkit.authorize_adaptive_action("wf-1", MaestroAction.ESCALATE)

    assert report.authorized is False
    assert report.requires_human_approval is False
    assert report.violations == ("contract violation",)
    assert report.warnings == ("review",)
    assert report.reason == "blocked by operating contract or human gate"
    kernel.intervene.assert_not_called()
