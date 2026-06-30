from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum


class GovernanceAction(StrEnum):
    keep = "keep"
    repair = "repair"
    retry = "retry"
    route_to_planner = "route_to_planner"
    freeze_agent = "freeze_agent"
    lower_priority = "lower_priority"
    escalate_to_human = "escalate_to_human"
    reject = "reject"


ACTION_MAP: dict[str, GovernanceAction] = {
    "flourishing": GovernanceAction.keep,
    "stable": GovernanceAction.keep,
    "hybrid": GovernanceAction.repair,
    "distorted": GovernanceAction.retry,
    "transient": GovernanceAction.repair,
    "extinct": GovernanceAction.reject,
    "accept_expand": GovernanceAction.keep,
    "accept": GovernanceAction.keep,
    "repair_scaffold": GovernanceAction.repair,
    "restructure": GovernanceAction.retry,
    "deepen_or_clarify": GovernanceAction.repair,
    "reject_regenerate": GovernanceAction.reject,
}


def map_to_governance_action(rank_or_policy: str) -> GovernanceAction:
    return ACTION_MAP.get(rank_or_policy, GovernanceAction.repair)


@dataclass
class PolicyDecision:
    action: GovernanceAction
    rank: str
    reward: float
    policy: str
    policy_label: str
    description: str
    action_label: str


@dataclass
class PolicyActionRecord:
    action: GovernanceAction
    rank: str
    reward: float
    policy: str
    timestamp: float
    eval_id: str = ""
    reason: str = ""


@dataclass
class PolicyContext:
    consecutive_failures: int = 0
    avg_reward: float = 0.0
    trend: str = "stable"
    priority: int = 1
    risk_level: str = "medium"
    agent_state: str = "active"
    history_count: int = 0


GOVERNANCE_ACTIONS_INFO: dict[str, dict[str, str]] = {
    "keep": {
        "label": "Keep - Accept Response",
        "description": "Accept the response as-is. The agent performed well.",
    },
    "repair": {
        "label": "Repair - Send Repair Prompt",
        "description": "Response has useful core but needs improvement. Send repair prompt back to agent.",
    },
    "retry": {
        "label": "Retry - Regenerate Response",
        "description": "Response is structurally unsound. Ask the agent to regenerate from scratch.",
    },
    "route_to_planner": {
        "label": "Route to Planner",
        "description": "Send the query to a planner agent for structured decomposition.",
    },
    "freeze_agent": {
        "label": "Freeze Agent",
        "description": "Immediately freeze the agent. Human review required.",
    },
    "lower_priority": {
        "label": "Lower Priority",
        "description": "Reduce agent priority due to sustained low performance.",
    },
    "escalate_to_human": {
        "label": "Escalate to Human",
        "description": "Human supervisor intervention required.",
    },
    "reject": {
        "label": "Reject Response",
        "description": "Reject the response. It fails to carry meaning.",
    },
}


class PolicyEngine:
    def __init__(self, max_history: int = 1000):
        self._history: list[PolicyActionRecord] = []
        self._max_history = max_history

    def decide(
        self,
        rank: str,
        reward: float,
        policy: str,
        policy_label: str,
        context: PolicyContext | None = None,
    ) -> PolicyDecision:
        ctx = context or PolicyContext()

        action = map_to_governance_action(rank)

        if rank == "distorted":
            action = GovernanceAction.retry

        if rank == "extinct":
            action = GovernanceAction.reject

        if ctx.consecutive_failures >= 3 and action not in (
            GovernanceAction.escalate_to_human,
            GovernanceAction.freeze_agent,
        ):
            action = GovernanceAction.escalate_to_human

        if ctx.consecutive_failures >= 5 and action != GovernanceAction.freeze_agent:
            action = GovernanceAction.freeze_agent

        if ctx.history_count >= 3 and ctx.avg_reward < 0.3 and action == GovernanceAction.keep:
            action = GovernanceAction.lower_priority

        info = GOVERNANCE_ACTIONS_INFO.get(action.value, {})
        return PolicyDecision(
            action=action,
            rank=rank,
            reward=reward,
            policy=policy,
            policy_label=policy_label,
            description=info.get("description", ""),
            action_label=info.get("label", action.value),
        )

    def record(self, decision: PolicyDecision, eval_id: str = "", reason: str = "") -> PolicyActionRecord:
        record = PolicyActionRecord(
            action=decision.action,
            rank=decision.rank,
            reward=decision.reward,
            policy=decision.policy,
            timestamp=time.time(),
            eval_id=eval_id,
            reason=reason,
        )
        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        return record

    @property
    def history(self) -> list[PolicyActionRecord]:
        return list(self._history)

    @property
    def action_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for r in self._history:
            dist[r.action.value] = dist.get(r.action.value, 0) + 1
        return dist

    def recent(self, n: int = 20) -> list[PolicyActionRecord]:
        return self._history[-n:]

    def clear_history(self) -> None:
        self._history.clear()


policy_engine = PolicyEngine()
