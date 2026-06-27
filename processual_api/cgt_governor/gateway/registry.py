"""CGT Governor Gateway — Agent Registry

Registry of all governed agents with CRUD and evaluation tracking.
Backed by a pluggable GatewayStorage (memory, JSON file, or database).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from .models import Agent, AgentState, EvaluationRecord, GatewayAction
from .storage import GatewayStorage, MemoryStorage, _agent_to_dict, _dict_to_agent, create_storage

logger = logging.getLogger("processual_api.cgt_governor.gateway.registry")


class AgentRegistry:
    """Registry of governed agents backed by a pluggable storage backend."""

    def __init__(self, storage: GatewayStorage | None = None):
        self._agents: dict[str, Agent] = {}
        self._storage = storage or MemoryStorage()
        self._load()

    def _load(self) -> None:
        """Load agents from storage on startup."""
        raw_list = self._storage.load_agents()
        for item in raw_list:
            agent = _dict_to_agent(item)
            self._agents[agent.agent_id] = agent
        if raw_list:
            logger.info("Loaded %d agents from storage", len(raw_list))

    def _persist(self) -> None:
        """Write current state to storage."""
        agents = [_agent_to_dict(a) for a in self._agents.values()]
        self._storage.save_agents(agents)

    def register(self, agent: Agent) -> str:
        self._agents[agent.agent_id] = agent
        self._persist()
        logger.info("Agent registered: %s (%s)", agent.agent_id, agent.name)
        return agent.agent_id

    def get(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def list(self, state: AgentState | None = None) -> list[Agent]:
        if state is None:
            return list(self._agents.values())
        return [a for a in self._agents.values() if a.state == state]

    def change_state(
        self,
        agent_id: str,
        new_state: AgentState,
        reason: str = "",
    ) -> Agent:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise KeyError(f"Agent not found: {agent_id}")

        if new_state == agent.state and new_state != AgentState.ESCALATED:
            return agent

        old_state = agent.state
        agent.state = new_state
        agent.last_state_change = datetime.now(UTC).isoformat()
        agent.last_state_reason = reason

        if new_state != AgentState.ACTIVE:
            agent.consecutive_failures = 0

        self._persist()
        logger.info(
            "Agent %s state: %s → %s (%s)",
            agent_id,
            old_state.value,
            new_state.value,
            reason,
        )
        return agent

    def add_evaluation(self, agent_id: str, record: EvaluationRecord) -> None:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise KeyError(f"Agent not found: {agent_id}")

        agent.evaluation_history.append(record)
        agent.performance_window.append(record.reward)

        if record.action_taken in (GatewayAction.BLOCK, GatewayAction.ESCALATE):
            agent.consecutive_failures += 1
        else:
            agent.consecutive_failures = 0

        self._persist()

    def agents_at_risk(self, threshold: float = 0.0) -> list[Agent]:
        return [a for a in self._agents.values() if a.state == AgentState.ACTIVE and a.average_reward < threshold]

    def count_by_state(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for a in self._agents.values():
            counts[a.state.value] = counts.get(a.state.value, 0) + 1
        return counts


gateway_registry = AgentRegistry(storage=create_storage())
