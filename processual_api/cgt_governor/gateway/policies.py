"""CGT Governor Gateway - fail-closed policy engine."""

from __future__ import annotations

from .governance_genome import GovernanceGate, governance_genome
from .models import Agent, AgentState, GatewayAction, GatewayDecision


class PolicyEngine:
    """Map qualified governance signals to authoritative gateway decisions."""

    @classmethod
    def decide(
        cls,
        agent: Agent,
        fate_vector: dict[str, float],
        rank: str,
        reward: float,
        policy: str,
        repair_prompt: str | None,
        risk_signals: dict[str, float] | None = None,
    ) -> GatewayDecision:
        signals = risk_signals or {}

        failed_gate = governance_genome.first_failed_gate(signals)
        if failed_gate is not None:
            labels = {
                GovernanceGate.CONSTITUTIVE_CONSTRAINT: (
                    "Constitutive Constraint - Fail Closed",
                    "A constitutive governance constraint was violated.",
                ),
                GovernanceGate.AUTHORIZATION: (
                    "Authorization Boundary - Fail Closed",
                    "Required authorization was not established.",
                ),
                GovernanceGate.EVIDENCE: (
                    "Evidence Gate - Fail Closed",
                    "Required governance evidence is missing.",
                ),
            }
            label, message = labels[failed_gate]
            return GatewayDecision(
                action=GatewayAction.BLOCK,
                rank=rank,
                reward=reward,
                policy=policy,
                policy_label=label,
                fate_vector=fate_vector,
                repair_prompt=None,
                agent_state=AgentState.ACTIVE,
                message=message,
                governance_gate=failed_gate.value,
            )

        hallucination = signals.get("hallucination", fate_vector.get("hallucination", 0.0))
        if rank == "extinct" and hallucination >= 0.3:
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
            decision = GatewayDecision(
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
        elif rank == "distorted":
            decision = GatewayDecision(
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
        elif rank == "hybrid":
            decision = GatewayDecision(
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
        elif rank == "transient":
            decision = GatewayDecision(
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
        else:
            decision = GatewayDecision(
                action=GatewayAction.PASS,
                rank=rank,
                reward=reward,
                policy=policy,
                policy_label=(
                    "Flourishing - Accept & Expand"
                    if rank == "flourishing"
                    else "Stable - Accept"
                ),
                fate_vector=fate_vector,
                repair_prompt=None,
                agent_state=AgentState.ACTIVE,
                message="Response approved. Agent performing well.",
            )

        if (
            agent.consecutive_failures >= governance_genome.consecutive_failure_escalation_limit
            and decision.action not in {GatewayAction.ESCALATE}
        ):
            return GatewayDecision(
                action=GatewayAction.ESCALATE,
                rank=rank,
                reward=reward,
                policy=policy,
                policy_label="Escalated - Human Review Required",
                fate_vector=fate_vector,
                repair_prompt=repair_prompt,
                agent_state=AgentState.ESCALATED,
                message=(
                    f"Agent {agent.agent_id} has {agent.consecutive_failures} "
                    "consecutive failures. Escalated."
                ),
            )

        return decision


policy_engine = PolicyEngine()
