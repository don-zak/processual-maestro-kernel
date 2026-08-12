from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, call

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit
from processual_kernel.audit import AuditEventType


def make_toolkit() -> AdaptiveGovernanceToolkit:
    toolkit = object.__new__(AdaptiveGovernanceToolkit)
    toolkit.kernel = Mock()
    toolkit.replay_lab = Mock()
    toolkit.profile_task = Mock()
    toolkit.select_policy = Mock()
    toolkit.workflow_history = Mock()
    toolkit._profiles = {}
    toolkit._policies = {}
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    return toolkit


def test_replay_history_delegates_audits_and_persists() -> None:
    toolkit = make_toolkit()
    baseline = SimpleNamespace(name="baseline")
    candidate = SimpleNamespace(name="candidate")
    history = (SimpleNamespace(event_type="checkpoint"),)
    comparison = SimpleNamespace(
        baseline_policy=SimpleNamespace(value="baseline"),
        candidate_policy=SimpleNamespace(value="candidate"),
        recommendation="prefer_candidate",
        confidence=0.82,
    )
    toolkit.replay_lab.replay_history.return_value = comparison

    result = toolkit.replay_history("wf-1", baseline, candidate, history)

    assert result is comparison
    toolkit.replay_lab.replay_history.assert_called_once_with(
        "wf-1", baseline, candidate, history
    )
    toolkit._audit_adaptive.assert_called_once_with(
        AuditEventType.REPLAY_COMPARISON,
        "wf-1",
        {
            "workflow_id": "wf-1",
            "baseline_policy": "baseline",
            "candidate_policy": "candidate",
            "recommendation": "prefer_candidate",
            "confidence": 0.82,
            "payload": comparison,
        },
    )
    toolkit._persist.assert_called_once_with("replay_comparisons", comparison)


def test_replay_counterfactuals_uses_cached_profile_policy_and_history() -> None:
    toolkit = make_toolkit()
    profile = SimpleNamespace(name="cached-profile")
    baseline = SimpleNamespace(name="cached-policy")
    candidates = (SimpleNamespace(name="candidate-a"), SimpleNamespace(name="candidate-b"))
    history = (SimpleNamespace(event_type="checkpoint"), SimpleNamespace(event_type="outcome"))
    first = SimpleNamespace(scenario="candidate-a", recommendation="prefer_scenario", confidence=0.7)
    second = SimpleNamespace(scenario="candidate-b", recommendation="keep_baseline", confidence=0.6)
    toolkit._profiles["wf-1"] = profile
    toolkit._policies["wf-1"] = baseline
    toolkit.workflow_history.return_value = history
    toolkit.replay_lab.counterfactual_scenarios.return_value = (first, second)

    results = toolkit.replay_counterfactuals("wf-1", candidate_policies=candidates)

    assert results == (first, second)
    toolkit.kernel.get_workflow.assert_not_called()
    toolkit.profile_task.assert_not_called()
    toolkit.select_policy.assert_not_called()
    toolkit.workflow_history.assert_called_once_with("wf-1")
    toolkit.replay_lab.counterfactual_scenarios.assert_called_once_with(
        "wf-1",
        baseline=baseline,
        history=history,
        candidate_policies=candidates,
    )
    assert toolkit._persist.call_args_list == [
        call("replay_scenarios", first),
        call("replay_scenarios", second),
    ]
    assert toolkit._audit_adaptive.call_args_list == [
        call(
            AuditEventType.REPLAY_SCENARIO,
            "wf-1",
            {
                "workflow_id": "wf-1",
                "scenario": "candidate-a",
                "recommendation": "prefer_scenario",
                "confidence": 0.7,
                "payload": first,
            },
        ),
        call(
            AuditEventType.REPLAY_SCENARIO,
            "wf-1",
            {
                "workflow_id": "wf-1",
                "scenario": "candidate-b",
                "recommendation": "keep_baseline",
                "confidence": 0.6,
                "payload": second,
            },
        ),
    ]


def test_replay_counterfactuals_profiles_and_selects_baseline_when_cache_empty() -> None:
    toolkit = make_toolkit()
    workflow = SimpleNamespace(workflow_id="wf-2")
    profile = SimpleNamespace(name="profile")
    baseline = SimpleNamespace(name="selected")
    history = ()
    toolkit.kernel.get_workflow.return_value = workflow
    toolkit.profile_task.return_value = profile
    toolkit.select_policy.return_value = baseline
    toolkit.workflow_history.return_value = history
    toolkit.replay_lab.counterfactual_scenarios.return_value = ()

    results = toolkit.replay_counterfactuals("wf-2")

    assert results == ()
    toolkit.kernel.get_workflow.assert_called_once_with("wf-2")
    toolkit.profile_task.assert_called_once_with(workflow)
    toolkit.select_policy.assert_called_once_with(profile, workflow_id="wf-2")
    toolkit.workflow_history.assert_called_once_with("wf-2")
    toolkit.replay_lab.counterfactual_scenarios.assert_called_once_with(
        "wf-2",
        baseline=baseline,
        history=history,
        candidate_policies=(),
    )
    toolkit._audit_adaptive.assert_not_called()
    toolkit._persist.assert_not_called()
