"""CGT Governor Gateway — public orchestration boundary.

Protected evaluation is intentionally not executed in the public gateway.
Active-agent evaluation requires a sanitized private decision path. Until that
provider composition is explicitly configured and approved, evaluation fails
closed before local analysis, scoring, vectors, signing, or persistence.
"""

from __future__ import annotations

import logging

from processual_api.integrations.private_evaluation_boundary import PrivateEvaluationUnavailableError

from .models import AgentState, GatewayAction, GatewayDecision
from .registry import gateway_registry

logger = logging.getLogger("processual_api.cgt_governor.gateway.engine")


class GatewayEngine:
    """Apply public agent-state admission before protected evaluation."""

    @staticmethod
    def evaluate(
        agent_id: str,
        client_query: str,
        agent_response: str,
        language: str = "en",
    ) -> GatewayDecision | None:
        """Admit an agent or fail closed before protected mathematical evaluation.

        Unknown agents still return ``None``. Agents that are not active remain
        administratively blocked without invoking protected evaluation. Active
        or rehabilitating agents require the controlled private evaluation
        boundary; the legacy local analyzer/vector path is deliberately disabled.
        """
        del client_query, agent_response, language

        agent = gateway_registry.get(agent_id)
        if agent is None:
            logger.warning("Gateway evaluate called for unknown agent: %s", agent_id)
            return None

        if agent.state not in (AgentState.ACTIVE, AgentState.REHABILITATING):
            return GatewayDecision(
                action=GatewayAction.BLOCK,
                rank="",
                reward=0.0,
                policy="",
                policy_label="Agent Not Available",
                fate_vector={},
                repair_prompt=None,
                agent_state=agent.state,
                message=f"Agent is {agent.state.value}. Cannot process requests.",
            )

        raise PrivateEvaluationUnavailableError("private_evaluation_unavailable")


gateway_engine = GatewayEngine()
