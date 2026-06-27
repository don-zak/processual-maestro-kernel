"""CGT Governor Gateway — Lifecycle Engine

Periodic evaluation of agent health and automatic state transitions:
  - UPGRADE: sustained high performance → recommend better model
  - FREEZE: sustained low performance → temporarily disable
  - REHABILITATE: medium performance with declining trend → retrain
  - ESCALATE: critical or recurring failures → human attention
"""

from __future__ import annotations

import logging

from .models import Agent, AgentState

logger = logging.getLogger("processual_api.cgt_governor.gateway.lifecycle")

UPGRADE_REWARD_THRESHOLD = 1.2
FREEZE_REWARD_THRESHOLD = -0.5
REHAB_REWARD_THRESHOLD = 0.0
TREND_WINDOW = 10
CONSECUTIVE_FREEZE_LIMIT = 5


class LifecycleEngine:
    """Analyzes agent history and recommends lifecycle actions."""

    @staticmethod
    def evaluate_agent(agent: Agent) -> str | None:
        """Return recommended action or None if no action needed."""
        if agent.state != AgentState.ACTIVE:
            return None

        if len(agent.evaluation_history) < 3:
            return None

        avg = agent.average_reward
        trend = agent.trend

        # ── FREEZE: sustained low performance ──
        if avg < FREEZE_REWARD_THRESHOLD:
            logger.warning(
                "Agent %s avg reward %.2f below freeze threshold — recommending freeze",
                agent.agent_id,
                avg,
            )
            return "freeze"

        # ── FREEZE: excessive consecutive failures ──
        if agent.consecutive_failures >= CONSECUTIVE_FREEZE_LIMIT:
            logger.warning(
                "Agent %s has %d consecutive failures — recommending freeze",
                agent.agent_id,
                agent.consecutive_failures,
            )
            return "freeze"

        # ── ESCALATE: declining trend near threshold ──
        if trend == "declining" and avg < REHAB_REWARD_THRESHOLD:
            logger.info(
                "Agent %s declining (avg %.2f) — recommending escalation",
                agent.agent_id,
                avg,
            )
            return "escalate"

        # ── UPGRADE: sustained high performance ──
        if avg >= UPGRADE_REWARD_THRESHOLD and trend == "improving":
            logger.info(
                "Agent %s excellent avg %.2f — recommending upgrade",
                agent.agent_id,
                avg,
            )
            return "upgrade"

        # ── REHABILITATE: low but not critical ──
        if avg < REHAB_REWARD_THRESHOLD:
            logger.info(
                "Agent %s avg %.2f below rehab threshold — recommending rehabilitation",
                agent.agent_id,
                avg,
            )
            return "rehabilitate"

        return None


lifecycle_engine = LifecycleEngine()
