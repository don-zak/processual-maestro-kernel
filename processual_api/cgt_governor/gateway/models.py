"""CGT Governor Gateway — Data Models

Agent lifecycle states (pending → active → frozen/escalated/rehabilitating/deactivated),
the Agent dataclass with evaluation history and trend computation,
EvaluationRecord for per-request governance snapshots,
and GatewayDecision for policy outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AgentState(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FROZEN = "frozen"
    ESCALATED = "escalated"
    REHABILITATING = "rehabilitating"
    DEACTIVATED = "deactivated"


class GatewayAction(StrEnum):
    PASS = "pass"  # nosec
    REPAIR = "repair"
    BLOCK = "block"
    ESCALATE = "escalate"


@dataclass
class EvaluationRecord:
    timestamp: str
    client_query: str
    agent_response: str
    rank: str
    reward: float
    policy: str
    policy_label: str
    fate_vector: dict[str, float]
    repair_prompt: str | None
    action_taken: GatewayAction
    language: str = "en"


@dataclass
class GatewayDecision:
    action: GatewayAction
    rank: str
    reward: float
    policy: str
    policy_label: str
    fate_vector: dict[str, float]
    repair_prompt: str | None
    agent_state: AgentState
    message: str
    signature: str | None = None


@dataclass
class Agent:
    agent_id: str
    name: str
    role: str
    adapter_name: str
    model: str
    system_prompt: str
    language: str
    state: AgentState
    created_at: str
    last_state_change: str
    last_state_reason: str
    evaluation_history: list[EvaluationRecord] = field(default_factory=list)
    performance_window: list[float] = field(default_factory=list)
    consecutive_failures: int = 0
    tags: list[str] = field(default_factory=list)
    priority: int = 1
    risk_level: str = "medium"
    owner: str = ""
    policy_profile: str = "default"

    @property
    def average_reward(self, window: int = 10) -> float:
        vals = self.performance_window[-window:]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def trend(self) -> str:
        vals = self.performance_window[-10:]
        if len(vals) < 3:
            return "insufficient_data"
        recent = sum(vals[-3:]) / 3
        older = sum(vals[:-3]) / (len(vals) - 3) if len(vals) > 3 else recent
        if recent > older + 0.1:
            return "improving"
        if recent < older - 0.1:
            return "declining"
        return "stable"
