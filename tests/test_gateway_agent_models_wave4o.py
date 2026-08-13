from __future__ import annotations

import pytest

from processual_api.cgt_governor.gateway.models import Agent, AgentState


def _agent(performance_window: list[float] | None = None) -> Agent:
    return Agent(
        agent_id="agent-1",
        name="Coverage Agent",
        role="tester",
        adapter_name="fake",
        model="test-model",
        system_prompt="system",
        language="en",
        state=AgentState.ACTIVE,
        created_at="2026-08-13T00:00:00Z",
        last_state_change="2026-08-13T00:00:00Z",
        last_state_reason="created",
        performance_window=list(performance_window or []),
    )


def test_average_reward_empty_and_custom_window() -> None:
    agent = _agent()
    assert agent.average_reward == 0.0

    agent.performance_window = [1.0, -1.0, 0.5, 1.0]
    assert agent.average_reward == pytest.approx(0.375)
    assert agent.average_reward.__class__ is float


def test_average_reward_uses_last_ten_values() -> None:
    agent = _agent([100.0] + [float(value) for value in range(10)])

    assert agent.average_reward == pytest.approx(4.5)


def test_trend_reports_insufficient_data_for_fewer_than_three_values() -> None:
    assert _agent([]).trend == "insufficient_data"
    assert _agent([0.2]).trend == "insufficient_data"
    assert _agent([0.2, 0.3]).trend == "insufficient_data"


def test_trend_three_values_is_stable_without_older_baseline() -> None:
    assert _agent([0.0, 0.5, 1.0]).trend == "stable"


def test_trend_detects_improving_and_declining_windows() -> None:
    improving = _agent([0.0, 0.0, 0.0, 0.6, 0.7, 0.8])
    declining = _agent([0.9, 0.8, 0.7, 0.1, 0.0, -0.1])

    assert improving.trend == "improving"
    assert declining.trend == "declining"


def test_trend_treats_small_changes_as_stable() -> None:
    agent = _agent([0.50, 0.50, 0.50, 0.55, 0.55, 0.55])

    assert agent.trend == "stable"


def test_trend_uses_only_last_ten_values() -> None:
    agent = _agent([10.0, 10.0] + [0.0] * 7 + [0.5, 0.5, 0.5])

    assert agent.trend == "improving"
