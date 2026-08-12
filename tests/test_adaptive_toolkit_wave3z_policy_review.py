from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, call

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit
from processual_kernel.audit import AuditEventType


def make_toolkit() -> AdaptiveGovernanceToolkit:
    toolkit = object.__new__(AdaptiveGovernanceToolkit)
    toolkit.kernel = Mock()
    toolkit._profiles = {}
    toolkit._policies = {}
    toolkit._checkpoint_reports = {}
    toolkit.evaluator = SimpleNamespace(outcomes={})
    toolkit.critic = Mock()
    toolkit.calibrator = Mock()
    toolkit.profile_task = Mock()
    toolkit.select_policy = Mock()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    return toolkit


def test_review_policy_uses_cached_profile_policy_and_evidence() -> None:
    toolkit = make_toolkit()
    profile = SimpleNamespace(name="profile")
    policy = SimpleNamespace(policy_version="policy-v1")
    checkpoint_a = SimpleNamespace(checkpoint_number=1)
    checkpoint_b = SimpleNamespace(checkpoint_number=2)
    outcome_a = SimpleNamespace(decision_id="dec-1")
    outcome_b = SimpleNamespace(decision_id="dec-2")
    critique = SimpleNamespace(
        policy_version="policy-v1",
        confidence=0.8,
        findings=("finding-a", "finding-b"),
        suggested_changes=("change-a",),
    )
    toolkit._profiles["wf-1"] = profile
    toolkit._policies["wf-1"] = policy
    toolkit._checkpoint_reports["wf-1"] = [checkpoint_a, checkpoint_b]
    toolkit.evaluator.outcomes = {"dec-1": outcome_a, "dec-2": outcome_b}
    toolkit.critic.review.return_value = critique

    result = toolkit.review_policy("wf-1")

    assert result is critique
    toolkit.profile_task.assert_not_called()
    toolkit.select_policy.assert_not_called()
    toolkit.critic.review.assert_called_once_with(
        toolkit.kernel,
        "wf-1",
        policy,
        checkpoints=(checkpoint_a, checkpoint_b),
        outcomes=(outcome_a, outcome_b),
    )
    toolkit._audit_adaptive.assert_called_once_with(
        AuditEventType.POLICY_CRITIQUE,
        "wf-1",
        {
            "workflow_id": "wf-1",
            "policy_version": "policy-v1",
            "confidence": 0.8,
            "finding_count": 2,
            "suggested_patch_count": 1,
            "payload": critique,
        },
    )


def test_review_policy_profiles_and_selects_when_cache_is_empty() -> None:
    toolkit = make_toolkit()
    workflow = SimpleNamespace(workflow_id="wf-2")
    profile = SimpleNamespace(name="fallback-profile")
    policy = SimpleNamespace(policy_version="policy-v2")
    critique = SimpleNamespace(
        policy_version="policy-v2",
        confidence=0.5,
        findings=(),
        suggested_changes=(),
    )
    toolkit.kernel.get_workflow.return_value = workflow
    toolkit.profile_task.return_value = profile
    toolkit.select_policy.return_value = policy
    toolkit.critic.review.return_value = critique

    result = toolkit.review_policy("wf-2")

    assert result is critique
    toolkit.kernel.get_workflow.assert_called_once_with("wf-2")
    toolkit.profile_task.assert_called_once_with(workflow)
    toolkit.select_policy.assert_called_once_with(profile, workflow_id="wf-2")
    toolkit.critic.review.assert_called_once_with(
        toolkit.kernel,
        "wf-2",
        policy,
        checkpoints=(),
        outcomes=(),
    )


def test_review_policy_honors_explicit_policy_without_reselecting() -> None:
    toolkit = make_toolkit()
    profile = SimpleNamespace(name="cached-profile")
    explicit_policy = SimpleNamespace(policy_version="explicit-v3")
    critique = SimpleNamespace(
        policy_version="explicit-v3",
        confidence=0.9,
        findings=("stable",),
        suggested_changes=(),
    )
    toolkit._profiles["wf-3"] = profile
    toolkit.critic.review.return_value = critique

    result = toolkit.review_policy("wf-3", policy=explicit_policy)

    assert result is critique
    toolkit.select_policy.assert_not_called()
    toolkit.critic.review.assert_called_once_with(
        toolkit.kernel,
        "wf-3",
        explicit_policy,
        checkpoints=(),
        outcomes=(),
    )


def test_suggest_policy_patches_audits_and_persists_recommendations() -> None:
    toolkit = make_toolkit()
    critique = SimpleNamespace(workflow_id="wf-4")
    patch_a = SimpleNamespace(
        policy_version_from="v1",
        policy_version_to="v2",
        field="checkpoint_interval",
        sample_size=12,
        runtime_mode=SimpleNamespace(value="recommend"),
        reason="tighten checkpoint cadence",
    )
    patch_b = SimpleNamespace(
        policy_version_from="v2",
        policy_version_to="v3",
        field="drift_sensitivity",
        sample_size=18,
        runtime_mode=SimpleNamespace(value="observe"),
        reason="increase drift sensitivity",
    )
    toolkit.calibrator.suggest_patch.return_value = (patch_a, patch_b)

    result = toolkit.suggest_policy_patches(critique, min_sample_size=10)

    assert result == (patch_a, patch_b)
    toolkit.calibrator.suggest_patch.assert_called_once_with(critique, min_sample_size=10)
    assert toolkit._audit_adaptive.call_args_list == [
        call(
            AuditEventType.POLICY_PATCH,
            "wf-4",
            {
                "workflow_id": "wf-4",
                "policy_version": "v1",
                "patch_field": "checkpoint_interval",
                "policy_version_to": "v2",
                "sample_size": 12,
                "runtime_mode": "recommend",
                "payload": patch_a,
            },
        ),
        call(
            AuditEventType.POLICY_PATCH,
            "wf-4",
            {
                "workflow_id": "wf-4",
                "policy_version": "v2",
                "patch_field": "drift_sensitivity",
                "policy_version_to": "v3",
                "sample_size": 18,
                "runtime_mode": "observe",
                "payload": patch_b,
            },
        ),
    ]
    assert len(toolkit._persist.call_args_list) == 2
    for persist_call, patch in zip(toolkit._persist.call_args_list, (patch_a, patch_b), strict=True):
        kind, history_entry = persist_call.args
        assert kind == "policy_patches"
        assert history_entry.patch is patch
        assert history_entry.status == "recommended"
        assert history_entry.workflow_id == "wf-4"
        assert history_entry.reason == patch.reason


def test_suggest_policy_patches_returns_empty_without_side_effects() -> None:
    toolkit = make_toolkit()
    critique = SimpleNamespace(workflow_id="wf-5")
    toolkit.calibrator.suggest_patch.return_value = ()

    result = toolkit.suggest_policy_patches(critique)

    assert result == ()
    toolkit.calibrator.suggest_patch.assert_called_once_with(critique, min_sample_size=None)
    toolkit._audit_adaptive.assert_not_called()
    toolkit._persist.assert_not_called()
