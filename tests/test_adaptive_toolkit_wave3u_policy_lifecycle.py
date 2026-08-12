from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit
from processual_kernel.adaptive_types import RuntimeMode
from processual_kernel.types import KernelPolicy


def make_toolkit() -> tuple[AdaptiveGovernanceToolkit, SimpleNamespace]:
    kernel = SimpleNamespace(
        policy=KernelPolicy(),
        governor=SimpleNamespace(policy=None),
        _audit=Mock(),
        get_workflow=Mock(return_value=object()),
    )
    return AdaptiveGovernanceToolkit(kernel), kernel


def test_decision_ledger_forwarders() -> None:
    toolkit, _ = make_toolkit()
    toolkit.ledger = Mock()
    decision = object()
    entry = object()
    toolkit.ledger.record.return_value = entry
    toolkit.ledger.pending.return_value = (entry,)
    toolkit.ledger.coverage_ratio.return_value = 0.75

    assert toolkit.record_decision(decision, workflow_id="wf-1", important=False, ticket="INC-1") is entry
    toolkit.ledger.record.assert_called_once_with(
        decision, workflow_id="wf-1", important=False, ticket="INC-1"
    )
    assert toolkit.pending_outcomes(important_only=False) == (entry,)
    toolkit.ledger.pending.assert_called_once_with(important_only=False)
    assert toolkit.outcome_coverage_ratio(important_only=False) == 0.75
    toolkit.ledger.coverage_ratio.assert_called_once_with(important_only=False)


def test_profile_policy_and_tempo_cache_when_workflow_id_is_supplied() -> None:
    toolkit, _ = make_toolkit()
    workflow = SimpleNamespace(workflow_id="wf-1")
    profile = object()
    policy = object()
    tempo = object()
    toolkit.profiler = Mock()
    toolkit.profiler.profile.return_value = profile
    toolkit.selector = Mock()
    toolkit.selector.select.return_value = policy
    toolkit.tempo_controller = Mock()
    toolkit.tempo_controller.plan.return_value = tempo

    assert toolkit.profile_task(workflow) is profile
    assert toolkit._profiles["wf-1"] is profile
    toolkit.profiler.profile.assert_called_once_with(workflow)

    assert toolkit.select_policy(profile, workflow_id="wf-1") is policy
    assert toolkit._policies["wf-1"] is policy
    toolkit.selector.select.assert_called_once_with(profile)

    assert toolkit.plan_tempo(profile, policy, workflow_id="wf-1") is tempo
    assert toolkit._tempo_plans["wf-1"] is tempo
    toolkit.tempo_controller.plan.assert_called_once_with(profile, policy)


def test_select_policy_and_plan_tempo_do_not_cache_without_workflow_id() -> None:
    toolkit, _ = make_toolkit()
    profile = object()
    policy = object()
    tempo = object()
    toolkit.selector = Mock()
    toolkit.selector.select.return_value = policy
    toolkit.tempo_controller = Mock()
    toolkit.tempo_controller.plan.return_value = tempo

    assert toolkit.select_policy(profile) is policy
    assert toolkit._policies == {}
    assert toolkit.plan_tempo(profile, policy) is tempo
    assert toolkit._tempo_plans == {}


def test_apply_policy_profile_updates_kernel_and_governor() -> None:
    toolkit, kernel = make_toolkit()
    selected = KernelPolicy()
    policy = SimpleNamespace(kernel_policy=selected)

    toolkit.apply_policy_profile(policy)

    assert kernel.policy is selected
    assert kernel.governor.policy is selected


def make_patch() -> SimpleNamespace:
    return SimpleNamespace(
        policy_version_from="p1",
        policy_version_to="p2",
        field="dt",
        sample_size=12,
        runtime_mode=RuntimeMode.RECOMMEND,
        reason="stable evidence",
    )


def test_suggest_policy_patches_audits_and_persists_each_patch() -> None:
    toolkit, _ = make_toolkit()
    toolkit.calibrator = Mock()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    critique = SimpleNamespace(workflow_id="wf-1")
    patch1 = make_patch()
    patch2 = make_patch()
    patch2.field = "min_psi"
    toolkit.calibrator.suggest_patch.return_value = (patch1, patch2)

    assert toolkit.suggest_policy_patches(critique, min_sample_size=10) == (patch1, patch2)
    toolkit.calibrator.suggest_patch.assert_called_once_with(critique, min_sample_size=10)
    assert toolkit._audit_adaptive.call_count == 2
    first_payload = toolkit._audit_adaptive.call_args_list[0].args[2]
    assert first_payload["workflow_id"] == "wf-1"
    assert first_payload["policy_version"] == "p1"
    assert first_payload["patch_field"] == "dt"
    assert first_payload["policy_version_to"] == "p2"
    assert first_payload["runtime_mode"] == RuntimeMode.RECOMMEND.value
    assert toolkit._persist.call_count == 2
    first_entry = toolkit._persist.call_args_list[0].args[1]
    assert first_entry.patch is patch1
    assert first_entry.status == "recommended"
    assert first_entry.workflow_id == "wf-1"


def test_apply_policy_patch_updates_policy_tracks_version_and_persists() -> None:
    toolkit, kernel = make_toolkit()
    toolkit.calibrator = Mock()
    toolkit.calibrator.mode = RuntimeMode.CONTROLLED_ADAPTIVE
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    patch = make_patch()
    updated = SimpleNamespace(policy_version="p2")
    toolkit.calibrator.apply_patch.return_value = updated
    original_policy = kernel.policy

    toolkit.apply_policy_patch(patch, min_sample_size=7)

    toolkit.calibrator.apply_patch.assert_called_once_with(original_policy, patch, min_sample_size=7)
    assert kernel.policy is updated
    assert kernel.governor.policy is updated
    assert "p2" in toolkit._successful_patch_versions
    payload = toolkit._audit_adaptive.call_args.args[2]
    assert payload["applied"] is True
    assert payload["runtime_mode"] == RuntimeMode.CONTROLLED_ADAPTIVE.value
    entry = toolkit._persist.call_args.args[1]
    assert entry.patch is patch
    assert entry.status == "applied"


def test_rollback_policy_patch_updates_policy_discards_version_and_persists() -> None:
    toolkit, kernel = make_toolkit()
    toolkit.calibrator = Mock()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    patch = make_patch()
    toolkit._successful_patch_versions.add("p2")
    updated = SimpleNamespace(policy_version="p1")
    toolkit.calibrator.rollback_patch.return_value = updated
    original_policy = kernel.policy

    toolkit.rollback_policy_patch(patch)

    toolkit.calibrator.rollback_patch.assert_called_once_with(original_policy, patch)
    assert kernel.policy is updated
    assert kernel.governor.policy is updated
    assert "p2" not in toolkit._successful_patch_versions
    payload = toolkit._audit_adaptive.call_args.args[2]
    assert payload["policy_version"] == "p1"
    assert payload["rolled_back"] is True
    entry = toolkit._persist.call_args.args[1]
    assert entry.patch is patch
    assert entry.status == "rolled_back"


def test_policy_patch_history_and_entries_preserve_lifecycle_order() -> None:
    toolkit, _ = make_toolkit()
    recommended = make_patch()
    applied = make_patch()
    rolled_back = make_patch()
    toolkit.calibrator = SimpleNamespace(
        patch_history=[recommended],
        applied_patches=[applied],
        rollback_history=[rolled_back],
    )

    assert toolkit.policy_patch_history() == (recommended, applied, rolled_back)
    entries = toolkit.policy_patch_history_entries()
    assert tuple(entry.patch for entry in entries) == (recommended, applied, rolled_back)
    assert tuple(entry.status for entry in entries) == ("recommended", "applied", "rolled_back")


def test_handle_cycle_patches_applies_safe_and_requests_gate_for_unsafe() -> None:
    toolkit, _ = make_toolkit()
    profile = object()
    policy = SimpleNamespace(min_sample_size=11)
    safe = make_patch()
    unsafe = make_patch()
    unsafe.field = "min_psi"
    toolkit.safety_guard = Mock()
    toolkit.safety_guard.can_auto_apply_patch.side_effect = [True, False]
    toolkit.apply_policy_patch = Mock()
    toolkit.request_human_approval = Mock()

    toolkit._handle_cycle_patches("wf-1", profile, policy, (safe, unsafe), True)

    toolkit.apply_policy_patch.assert_called_once_with(safe, min_sample_size=11)
    toolkit.request_human_approval.assert_called_once_with(
        "wf-1",
        "policy_patch",
        "policy patch requires human approval or is not eligible for automatic application",
        policy_version=unsafe.policy_version_from,
        patch_field=unsafe.field,
        policy_version_to=unsafe.policy_version_to,
        runtime_mode=toolkit.mode.value,
    )


def test_handle_cycle_patches_returns_early_when_disabled_or_empty() -> None:
    toolkit, _ = make_toolkit()
    toolkit.safety_guard = Mock()
    profile = object()
    policy = object()

    toolkit._handle_cycle_patches("wf-1", profile, policy, (), True)
    toolkit._handle_cycle_patches("wf-1", profile, policy, (make_patch(),), False)

    toolkit.safety_guard.can_auto_apply_patch.assert_not_called()
