"""CGT Governor — public simulation orchestration boundary.

The historical simulation pipeline generated local scores and fate vectors in
public code. That behavior is intentionally disabled as a protected-evaluation
fallback. Simulation may resume only from sanitized private decisions through a
separately reviewed boundary-aware implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

from processual_api.integrations.private_evaluation_boundary import PrivateEvaluationUnavailableError

from .agents import AgentPersona


@dataclass
class AgentEvaluation:
    """Legacy simulation result shape retained for import compatibility only."""

    agent: AgentPersona
    scenario_title: str
    rank: str
    reward: float
    policy: str
    policy_label: str
    fate_vector: dict
    repair_prompt: str | None = None


@dataclass
class SimulationResult:
    """Legacy simulation report shape retained for import compatibility only."""

    simulation_id: str
    ts: str
    evaluations: list[AgentEvaluation]
    rank_distribution: dict[str, int]
    avg_reward: float
    highest_agent: str | None
    lowest_agent: str | None
    risk_count: int


class SimulationEngine:
    """Fail closed until simulation consumes sanitized private decisions."""

    _counter: int = 0

    @classmethod
    def run(cls, language: str = "en", use_analyzer: bool = True) -> SimulationResult:
        """Reject legacy local protected evaluation in the public runtime."""
        del language, use_analyzer
        raise PrivateEvaluationUnavailableError("private_evaluation_unavailable")


simulation_engine = SimulationEngine()
