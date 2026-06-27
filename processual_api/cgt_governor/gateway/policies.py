"""CGT Governor Gateway - Policy Engine

Decision rules that map evaluation results to gateway actions:
  PASS     -> response approved, agent continues
  REPAIR   -> response needs repair prompt, loop back
  BLOCK    -> response rejected immediately
  ESCALATE -> human supervisor notified
"""

from __future__ import annotations

from .models import Agent, AgentState, GatewayAction, GatewayDecision


class PolicyEngine:
    """Evaluates governance rules and returns a GatewayDecision."""

    @classmethod
    def decide(
        cls,
        agent: Agent,
        fate_vector: dict,
        rank: str,
        reward: float,
        policy: str,
        repair_prompt: str | None,
    ) -> GatewayDecision:
        """Apply rule chain to produce a gateway decision."""

        # -- Rule 1: Critical failure -> BLOCK + FREEZE --
        if rank == "extinct" and fate_vector.get("hallucination", 0) >= 0.3:
            return GatewayDecision(
                action=GatewayAction.BLOCK,
                rank=rank,
                reward=reward,
                policy=policy,
                policy_label="Extinct - Reject & Regenerate",
                fate_vector=fate_vector,
                repair_prompt=None,
                agent_state=AgentState.FROZEN,
                message="Critical failure: agent hallucinating. Frozen for review.",
            )

        if rank == "extinct":
            return GatewayDecision(
                action=GatewayAction.BLOCK,
                rank=rank,
                reward=reward,
                policy=policy,
                policy_label="Extinct - Reject & Regenerate",
                fate_vector=fate_vector,
                repair_prompt=None,
                agent_state=AgentState.ACTIVE,
                message="Response rejected: fails to carry meaning.",
            )

        # -- Rule 2: DISTORTED -> BLOCK (restructure needed) --
        if rank == "distorted":
            return GatewayDecision(
                action=GatewayAction.BLOCK,
                rank=rank,
                reward=reward,
                policy=policy,
                policy_label="Distorted - Restructure",
                fate_vector=fate_vector,
                repair_prompt=repair_prompt,
                agent_state=AgentState.ACTIVE,
                message="Response structurally distorted. Blocked. Repair prompt generated.",
            )

        # -- Rule 3: Recurring failures -> ESCALATE --
        if agent.consecutive_failures >= 3:
            return GatewayDecision(
                action=GatewayAction.ESCALATE,
                rank=rank,
                reward=reward,
                policy=policy,
                policy_label="Escalated - Human Review Required",
                fate_vector=fate_vector,
                repair_prompt=repair_prompt,
                agent_state=AgentState.ESCALATED,
                message=f"Agent {agent.agent_id} has {agent.consecutive_failures} consecutive failures. Escalated.",
            )

        # -- Rule 4: HYBRID -> REPAIR --
        if rank == "hybrid":
            return GatewayDecision(
                action=GatewayAction.REPAIR,
                rank=rank,
                reward=reward,
                policy=policy,
                policy_label="Hybrid - Repair & Scaffold",
                fate_vector=fate_vector,
                repair_prompt=repair_prompt,
                agent_state=AgentState.ACTIVE,
                message="Response has useful core but incomplete. Repair prompt sent to agent.",
            )

        # -- Rule 5: TRANSIENT -> REPAIR --
        if rank == "transient":
            return GatewayDecision(
                action=GatewayAction.REPAIR,
                rank=rank,
                reward=reward,
                policy=policy,
                policy_label="Transient - Deepen or Clarify",
                fate_vector=fate_vector,
                repair_prompt=repair_prompt,
                agent_state=AgentState.ACTIVE,
                message="Response is superficial. Deepen prompt sent to agent.",
            )

        # -- Rule 6: STABLE / FLOURISHING -> PASS --
        return GatewayDecision(
            action=GatewayAction.PASS,
            rank=rank,
            reward=reward,
            policy=policy,
            policy_label=("Flourishing - Accept & Expand" if rank == "flourishing" else "Stable - Accept"),
            fate_vector=fate_vector,
            repair_prompt=None,
            agent_state=AgentState.ACTIVE,
            message="Response approved. Agent performing well.",
        )


policy_engine = PolicyEngine()
