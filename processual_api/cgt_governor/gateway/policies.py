"""CGT Governor Gateway - Policy Engine

Decision rules that map evaluation results to gateway actions:
  PASS     -> response approved, agent continues
  REPAIR   -> response needs repair prompt, loop back
  BLOCK    -> response rejected immediately
  ESCALATE -> human supervisor notified
"""

from __future__ import annotations

from .models import Agent, AgentState, GatewayAction, GatewayDecision

_CONSECUTIVE_FAILURE_ESCALATION_LIMIT = 3


class PolicyEngine:
    """Evaluates governance rules and returns a GatewayDecision."""

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
        """Apply the gateway rule chain to the current evaluation.

        ``risk_signals`` contains analyzer-level evidence (for example,
        hallucination) that must not be mixed into the seven-component CGT
        fate vector. Consecutive-failure escalation is computed prospectively,
        so the current non-pass result is included in the threshold and a
        successful current result is never escalated solely because of stale
        failure history.
        """
        signals = risk_signals or {}

        # Critical analyzer evidence is fail-closed and takes precedence over
        # ordinary recurrence handling.
        if rank == "extinct" and signals.get("hallucination", 0.0) >= 0.3:
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

        # First determine the action implied by the current result. Recurrence
        # is evaluated only after this base decision exists.
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
                policy_label=("Flourishing - Accept & Expand" if rank == "flourishing" else "Stable - Accept"),
                fate_vector=fate_vector,
                repair_prompt=None,
                agent_state=AgentState.ACTIVE,
                message="Response approved. Agent performing well.",
            )

        # A non-pass current result extends the current failure streak. This
        # avoids the previous off-by-one behavior and allows repeated REPAIR
        # outcomes to trigger supervision. PASS is intentionally excluded: a
        # recovered agent should clear its streak rather than be escalated.
        if decision.action in (GatewayAction.REPAIR, GatewayAction.BLOCK):
            projected_failures = agent.consecutive_failures + 1
            if projected_failures >= _CONSECUTIVE_FAILURE_ESCALATION_LIMIT:
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
                        f"Agent {agent.agent_id} reached {projected_failures} "
                        "consecutive non-pass evaluations. Escalated."
                    ),
                )

        return decision


policy_engine = PolicyEngine()
