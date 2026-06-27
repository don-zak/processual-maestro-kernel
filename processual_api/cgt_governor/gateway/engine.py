"""CGT Governor Gateway — Engine

Orchestrates evaluation → policy → decision → lifecycle for an agent response.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from ..security import sign_response
from .lifecycle import lifecycle_engine
from .models import (
    AgentState,
    EvaluationRecord,
    GatewayAction,
    GatewayDecision,
)
from .policies import policy_engine
from .registry import gateway_registry

logger = logging.getLogger("processual_api.cgt_governor.gateway.engine")


class GatewayEngine:
    """Evaluates an agent response through the full governance pipeline."""

    @staticmethod
    def evaluate(
        agent_id: str,
        client_query: str,
        agent_response: str,
        language: str = "en",
    ) -> GatewayDecision | None:
        """Evaluate a single agent response and return a gateway decision.

        Returns None if agent not found.
        """
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

        # ── 1. Analyze answer & Run CGT Governor ──
        from ..analyzer import analyze_cgt
        from ..governor import govern_answer

        scores = analyze_cgt(client_query, agent_response, language=language)
        result = govern_answer(
            answer=agent_response,
            **scores,
            language=language,
        )

        fate_vector = {
            "stability": result.fate.stability,
            "hybridity": result.fate.hybridity,
            "distortion": result.fate.distortion,
            "extinction": result.fate.extinction,
            "collapse": result.fate.collapse,
            "flourishing": result.fate.flourishing,
            "transient": result.fate.transient,
        }

        # ── 2. Apply policies ──
        decision = policy_engine.decide(
            agent=agent,
            fate_vector=fate_vector,
            rank=result.rank.value,
            reward=result.reward,
            policy=result.policy,
            repair_prompt=result.repair_prompt,
        )

        # ── 3. Sign the decision ──
        decision.signature = sign_response(
            {
                "agent_id": agent_id,
                "action": decision.action.value,
                "rank": decision.rank,
                "reward": decision.reward,
                "ts": datetime.now(UTC).isoformat(),
            }
        )

        # ── 4. Record evaluation ──
        record = EvaluationRecord(
            timestamp=datetime.now(UTC).isoformat(),
            client_query=client_query,
            agent_response=agent_response,
            rank=result.rank.value,
            reward=result.reward,
            policy=result.policy,
            policy_label=result.policy_label,
            fate_vector=fate_vector,
            repair_prompt=result.repair_prompt,
            action_taken=decision.action,
            language=language,
        )
        gateway_registry.add_evaluation(agent_id, record)

        # ── 5. Apply state change if needed ──
        if decision.agent_state != agent.state:
            reason = f"Gateway policy: {decision.action.value} — {decision.message}"
            gateway_registry.change_state(
                agent_id,
                decision.agent_state,
                reason,
            )

        # ── 6. Check lifecycle for long-term actions ──
        lifecycle_action = lifecycle_engine.evaluate_agent(agent)
        if lifecycle_action == "freeze" and agent.state == AgentState.ACTIVE:
            gateway_registry.change_state(
                agent_id,
                AgentState.FROZEN,
                f"Lifecycle: sustained low performance (avg {agent.average_reward:.2f})",
            )
        elif lifecycle_action == "escalate":
            gateway_registry.change_state(
                agent_id,
                AgentState.ESCALATED,
                "Lifecycle: declining performance trend",
            )

        return decision


gateway_engine = GatewayEngine()
