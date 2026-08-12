from __future__ import annotations

from dataclasses import replace

import pytest

from processual_kernel.adaptive.policy_profiles import build_policy_profiles
from processual_kernel.adaptive.strategy_bandit import StrategyBandit
from processual_kernel.adaptive.task_profiler import TaskProfiler, _enum_value
from processual_kernel.adaptive.tempo_controller import TempoController
from processual_kernel.adaptive_types import (
    AgentCountBand,
    AmbiguityLevel,
    ExecutionTempo,
    PolicyName,
    RiskLevel,
    TaskDuration,
    TaskProfile,
    TaskSize,
)
from processual_kernel.types import MaestroAction, WorkflowPlan, WorkflowRecord, WorkflowStep


def _steps(count: int, *, preferred: tuple[str | None, ...] | None = None) -> tuple[WorkflowStep, ...]:
    preferred = preferred or (None,) * count
    return tuple(
        WorkflowStep(
            step_id=f"s{index}",
            capability="work",
            instruction=f"step {index}",
            preferred_agent_id=preferred[index],
        )
        for index in range(count)
    )


def _plan(count: int = 1, **metadata) -> WorkflowPlan:
    return WorkflowPlan(workflow_id="wf", goal="test", steps=_steps(count), metadata=metadata)


def _profile(
    *,
    size: TaskSize = TaskSize.MEDIUM,
    duration: TaskDuration = TaskDuration.MEDIUM,
    risk: RiskLevel = RiskLevel.MEDIUM,
    ambiguity: AmbiguityLevel = AmbiguityLevel.MEDIUM,
) -> TaskProfile:
    return TaskProfile(
        size=size,
        duration=duration,
        risk=risk,
        ambiguity=ambiguity,
        agent_count=AgentCountBand.FEW,
    )


def test_enum_value_accepts_enum_normalizes_strings_and_defaults() -> None:
    assert _enum_value(TaskSize, TaskSize.LARGE, TaskSize.SMALL) is TaskSize.LARGE
    assert _enum_value(AgentCountBand, "few_agents", AgentCountBand.SINGLE) is AgentCountBand.FEW
    assert _enum_value(TaskSize, " LARGE ", TaskSize.SMALL) is TaskSize.LARGE
    assert _enum_value(TaskSize, "unknown", TaskSize.MEDIUM) is TaskSize.MEDIUM
    assert _enum_value(TaskSize, 3, TaskSize.MEDIUM) is TaskSize.MEDIUM


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, TaskSize.SMALL), (3, TaskSize.SMALL), (4, TaskSize.MEDIUM), (8, TaskSize.MEDIUM), (9, TaskSize.LARGE)],
)
def test_task_profiler_size_heuristics(count: int, expected: TaskSize) -> None:
    assert TaskProfiler._size_from_steps(count) is expected


@pytest.mark.parametrize(
    ("count", "minutes", "expected"),
    [
        (1, 0, TaskDuration.SHORT),
        (1, 19, TaskDuration.SHORT),
        (1, 20, TaskDuration.MEDIUM),
        (1, 59, TaskDuration.MEDIUM),
        (1, 60, TaskDuration.LONG),
        (3, None, TaskDuration.SHORT),
        (4, None, TaskDuration.MEDIUM),
        (8, None, TaskDuration.MEDIUM),
        (9, None, TaskDuration.LONG),
    ],
)
def test_task_profiler_duration_heuristics(count: int, minutes: int | None, expected: TaskDuration) -> None:
    assert TaskProfiler._duration_from_estimate(count, minutes) is expected


def test_task_profiler_metadata_overrides_and_workflow_record() -> None:
    plan = WorkflowPlan(
        workflow_id="wf-meta",
        goal="metadata",
        steps=_steps(2, preferred=("a", "b")),
        metadata={
            "size": "large",
            "duration": "long",
            "risk": "high",
            "ambiguity": "low",
            "agent_count": "many_agents",
            "budget_sensitivity": "critical",
            "estimated_minutes": "75",
            "requires_audit": False,
        },
    )

    profile = TaskProfiler().profile(WorkflowRecord(plan=plan))

    assert profile.size is TaskSize.LARGE
    assert profile.duration is TaskDuration.LONG
    assert profile.risk is RiskLevel.HIGH
    assert profile.ambiguity is AmbiguityLevel.LOW
    assert profile.agent_count is AgentCountBand.MANY
    assert profile.budget_sensitivity is RiskLevel.CRITICAL
    assert profile.estimated_minutes == 75
    assert profile.requires_hourly_checkpoint is True
    assert profile.requires_audit is True
    assert profile.metadata["estimated_minutes"] == "75"


def test_task_profiler_invalid_metadata_falls_back_to_inference() -> None:
    profile = TaskProfiler().profile(
        _plan(
            5,
            size="invalid",
            duration="invalid",
            risk="invalid",
            ambiguity="invalid",
            agent_count="invalid",
            budget_sensitivity="invalid",
            estimated_minutes="not-a-number",
            sensitive=True,
            exploratory=True,
            requires_audit=False,
        )
    )

    assert profile.size is TaskSize.MEDIUM
    assert profile.duration is TaskDuration.MEDIUM
    assert profile.risk is RiskLevel.HIGH
    assert profile.ambiguity is AmbiguityLevel.HIGH
    assert profile.agent_count is AgentCountBand.MANY
    assert profile.budget_sensitivity is RiskLevel.MEDIUM
    assert profile.estimated_minutes is None
    assert profile.requires_hourly_checkpoint is False
    assert profile.requires_audit is True


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"critical": True}, RiskLevel.CRITICAL),
        ({"safety_critical": True}, RiskLevel.CRITICAL),
        ({"human_approval_required": True}, RiskLevel.HIGH),
        ({"sensitive": True}, RiskLevel.HIGH),
        ({}, RiskLevel.MEDIUM),
    ],
)
def test_task_profiler_risk_inference(metadata: dict[str, object], expected: RiskLevel) -> None:
    assert TaskProfiler._risk_from_metadata(metadata) is expected


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"ambiguity_score": 0.67}, AmbiguityLevel.HIGH),
        ({"ambiguity_score": "0.34"}, AmbiguityLevel.MEDIUM),
        ({"ambiguity_score": 0.33}, AmbiguityLevel.LOW),
        ({"ambiguity_score": "bad", "research": True}, AmbiguityLevel.HIGH),
        ({"exploratory": True}, AmbiguityLevel.HIGH),
        ({}, AmbiguityLevel.MEDIUM),
    ],
)
def test_task_profiler_ambiguity_inference(metadata: dict[str, object], expected: AmbiguityLevel) -> None:
    assert TaskProfiler._ambiguity_from_metadata(metadata) is expected


def test_task_profiler_agent_count_prefers_distinct_named_agents() -> None:
    single = WorkflowPlan("one", "goal", _steps(3, preferred=("a", "a", "a")))
    few = WorkflowPlan("few", "goal", _steps(5, preferred=("a", "b", "c", "d", "a")))
    many = WorkflowPlan("many", "goal", _steps(5, preferred=(None, None, None, None, None)))

    assert TaskProfiler._agent_count_from_plan(single) is AgentCountBand.SINGLE
    assert TaskProfiler._agent_count_from_plan(few) is AgentCountBand.FEW
    assert TaskProfiler._agent_count_from_plan(many) is AgentCountBand.MANY


@pytest.mark.parametrize(
    ("profile", "tempo", "threshold", "monitor"),
    [
        (_profile(risk=RiskLevel.CRITICAL), ExecutionTempo.INTENSIVE, 0.80, True),
        (_profile(risk=RiskLevel.HIGH), ExecutionTempo.CAUTIOUS, 0.85, True),
        (_profile(duration=TaskDuration.LONG), ExecutionTempo.BALANCED, 0.90, True),
        (_profile(size=TaskSize.LARGE), ExecutionTempo.BALANCED, 0.90, True),
        (
            _profile(size=TaskSize.SMALL, duration=TaskDuration.SHORT, risk=RiskLevel.LOW),
            ExecutionTempo.FAST,
            0.95,
            False,
        ),
        (_profile(), ExecutionTempo.BALANCED, 0.90, True),
    ],
)
def test_tempo_controller_maps_profile_to_execution_plan(
    profile: TaskProfile, tempo: ExecutionTempo, threshold: float, monitor: bool
) -> None:
    policy = build_policy_profiles()[PolicyName.BALANCED]
    plan = TempoController().plan(profile, policy)

    assert plan.tempo is tempo
    assert plan.budget_stop_threshold == threshold
    assert plan.monitor_drift is monitor
    assert plan.max_agents == policy.max_agents
    assert plan.max_retries == policy.max_retries
    assert plan.checkpoint_interval_minutes == policy.checkpoint_interval_minutes
    assert plan.notes == ("tempo derived from profile",)


def test_tempo_controller_disables_parallelism_only_for_cautious_mode() -> None:
    policy = build_policy_profiles()[PolicyName.QUALITY_FIRST]
    cautious = TempoController().plan(_profile(risk=RiskLevel.HIGH), policy)
    intensive = TempoController().plan(_profile(risk=RiskLevel.CRITICAL), policy)

    assert policy.parallel_execution is True
    assert cautious.allow_parallel_execution is False
    assert intensive.allow_parallel_execution is True


def test_strategy_bandit_clips_rewards_uses_profile_bucket_and_selects_best() -> None:
    bandit = StrategyBandit(min_sample_size=3)
    profile = _profile(risk=RiskLevel.LOW)

    for reward in (-2.0, 0.8, 2.0):
        bandit.record(MaestroAction.RETRY, reward, profile)
    for reward in (0.2, 0.3, 0.4):
        bandit.record(MaestroAction.REROUTE, reward, profile)

    suggestion = bandit.suggest(profile)
    bucket = StrategyBandit._bucket(profile)

    assert suggestion.strategy is MaestroAction.RETRY
    assert suggestion.sample_size == 3
    assert suggestion.confidence == pytest.approx(0.6)
    assert bucket in suggestion.reason
    assert suggestion.safe_to_apply is False
    assert bandit._stats[bucket][MaestroAction.RETRY] == [0.0, 0.8, 1.0]
    assert bandit._stats[StrategyBandit.GLOBAL_BUCKET][MaestroAction.RETRY] == [0.0, 0.8, 1.0]


def test_strategy_bandit_global_fallback_insufficient_and_critical_paths() -> None:
    bandit = StrategyBandit(min_sample_size=2)
    learned = _profile(size=TaskSize.SMALL, risk=RiskLevel.LOW, ambiguity=AmbiguityLevel.LOW)
    unseen = _profile(size=TaskSize.LARGE, risk=RiskLevel.MEDIUM, ambiguity=AmbiguityLevel.HIGH)

    assert bandit.suggest(unseen).strategy is MaestroAction.OBSERVE
    assert bandit.suggest(unseen).sample_size == 0

    bandit.record(MaestroAction.PAUSE, 0.7, learned)
    bandit.record(MaestroAction.PAUSE, 0.9, learned)
    fallback = bandit.suggest(unseen)

    assert fallback.strategy is MaestroAction.PAUSE
    assert fallback.confidence == pytest.approx(0.8)
    assert fallback.sample_size == 2
    assert StrategyBandit.GLOBAL_BUCKET in fallback.reason

    critical = bandit.suggest(replace(unseen, risk=RiskLevel.CRITICAL))
    assert critical.strategy is MaestroAction.ESCALATE
    assert critical.confidence == 0.0
    assert critical.sample_size == 0
    assert critical.safe_to_apply is False
    assert "human-gated" in critical.reason


def test_strategy_bandit_global_record_bucket_helpers_and_sample_gate() -> None:
    bandit = StrategyBandit(min_sample_size=2)
    profile = _profile()

    bandit.record(MaestroAction.OBSERVE, 0.4)
    assert StrategyBandit._bucket(None) == StrategyBandit.GLOBAL_BUCKET
    assert StrategyBandit._bucket(profile) == "medium|medium|medium|medium"
    assert bandit._best(StrategyBandit.GLOBAL_BUCKET) == (None, None, StrategyBandit.GLOBAL_BUCKET)

    bandit.record(MaestroAction.OBSERVE, 0.6)
    strategy, scores, source = bandit._best(StrategyBandit.GLOBAL_BUCKET)
    assert strategy is MaestroAction.OBSERVE
    assert scores == [0.4, 0.6]
    assert source == StrategyBandit.GLOBAL_BUCKET


def test_strategy_bandit_json_round_trip(tmp_path) -> None:
    path = tmp_path / "bandit.json"
    profile = _profile(size=TaskSize.SMALL, duration=TaskDuration.SHORT, risk=RiskLevel.LOW)
    original = StrategyBandit(min_sample_size=2)
    original.record(MaestroAction.RETRY, 0.25, profile)
    original.record(MaestroAction.RETRY, 0.75, profile)
    original.record(MaestroAction.REROUTE, 0.5)

    original.export_json(path)
    restored = StrategyBandit(min_sample_size=2)
    restored.record(MaestroAction.PAUSE, 1.0)
    restored.import_json(path)

    assert "retry" in path.read_text(encoding="utf-8")
    assert MaestroAction.PAUSE not in restored._stats[StrategyBandit.GLOBAL_BUCKET]
    assert restored.suggest(profile).strategy is MaestroAction.RETRY
    assert restored.suggest(profile).confidence == pytest.approx(0.5)
