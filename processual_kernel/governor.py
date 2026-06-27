from __future__ import annotations

from cgtlib import ExistenceRank, StructuralTransitionReport

from .types import (
    AgentCriticality,
    AgentRecord,
    AgentState,
    Coefficients,
    EdgeDecision,
    GovernanceDecision,
    HandoffRecord,
    KernelPolicy,
    MaestroAction,
    WorkflowDecision,
    WorkflowRecord,
    WorkflowState,
)


class LifecycleGovernor:
    """Deterministic lifecycle policy using Ψ and cgtlib structural transition outputs."""

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, value))

    def _confidence(self, coeff: Coefficients, report: StructuralTransitionReport) -> float:
        structural_strength = (report.retention + report.compatibility + (1.0 - report.transition_channel)) / 3.0
        risk_penalty = max(coeff.C, coeff.M) * 0.25
        fate_adjustment = 0.0
        if report.fate_vector is not None:
            fate_adjustment = (
                0.12 * report.fate_vector.stability
                + 0.10 * report.fate_vector.flourishing
                - 0.10 * report.fate_vector.distortion
                - 0.14 * report.fate_vector.extinction
            )
        return round(self._clamp(structural_strength + fate_adjustment - risk_penalty), 4)

    @staticmethod
    def _rank(report: StructuralTransitionReport) -> ExistenceRank | None:
        return report.existence_rank

    def __init__(self, policy: KernelPolicy | None = None):
        self.policy = policy or KernelPolicy()

    def decide(
        self,
        record: AgentRecord,
        coeff: Coefficients,
        dpsi: float,
        report: StructuralTransitionReport,
        cgt_dict: dict,
    ) -> GovernanceDecision:
        p = self.policy
        previous_state = record.state
        reason = "stable"
        new_state = previous_state
        review = False

        critical = record.spec.criticality == AgentCriticality.CRITICAL
        high_risk = coeff.M >= p.quarantine_policy_risk or coeff.C >= p.quarantine_policy_risk
        rank = self._rank(report)

        if high_risk:
            new_state = AgentState.QUARANTINED
            reason = "high policy/mortality risk"
            review = True
        elif previous_state == AgentState.ARCHIVED:
            if (
                coeff.N >= p.reactivation_need
                and report.compatibility >= 0.55
                and report.aftermath.balance >= p.min_aftermath_balance
            ):
                new_state = AgentState.TRANSITIONAL
                reason = "reactivation candidate: demand recovered"
                review = critical
            else:
                new_state = AgentState.ARCHIVED
                reason = "archived: demand or compatibility insufficient"
        elif (
            critical
            and p.critical_requires_review
            and (
                dpsi < -p.alpha
                or report.transition_channel >= p.max_transition_channel
                or report.aftermath.balance < p.min_aftermath_balance
            )
        ):
            new_state = AgentState.TRANSITIONAL
            reason = "critical agent degraded: human review required"
            review = True
        elif (not critical) and rank == ExistenceRank.EXTINCT:
            new_state = AgentState.ARCHIVED
            reason = "CGT existence rank extinct: no viable carrier/effect"
        elif rank == ExistenceRank.DISTORTED and dpsi < 0:
            new_state = AgentState.TRANSITIONAL
            reason = "CGT distorted rank: repair or simplify before reuse"
            review = record.spec.criticality in (AgentCriticality.HIGH, AgentCriticality.CRITICAL)
        elif record.failure_streak >= p.max_failure_streak:
            new_state = AgentState.TRANSITIONAL
            reason = "failure streak exceeded"
            review = record.spec.criticality in (AgentCriticality.HIGH, AgentCriticality.CRITICAL)
        elif critical and record.psi <= p.archive_max_psi:
            new_state = AgentState.TRANSITIONAL
            reason = "critical agent low Ψ: human review required before archive"
            review = True
        elif (
            (not critical)
            and record.psi <= p.archive_max_psi
            and report.retention < p.min_retention
            and report.aftermath.balance < p.min_aftermath_balance
        ):
            new_state = AgentState.ARCHIVED
            reason = "low Ψ with weak retention and negative aftermath"
        elif dpsi < -p.alpha or report.transition_channel >= p.max_transition_channel:
            new_state = AgentState.TRANSITIONAL
            reason = "autophagic trigger: Ψ is decaying or transition channel is high"
        elif record.psi >= p.active_min_psi and report.retention >= p.min_retention:
            new_state = AgentState.ACTIVE
            reason = "healthy Ψ and acceptable retention"
        else:
            new_state = previous_state
            reason = "hysteresis: no safe state change"

        return GovernanceDecision(
            agent_id=record.spec.agent_id,
            previous_state=previous_state,
            new_state=new_state,
            psi=record.psi,
            dpsi=dpsi,
            coefficients=coeff,
            reason=reason,
            cgt=cgt_dict,
            requires_human_review=review,
            confidence=self._confidence(coeff, report),
            policy_version=p.policy_version,
        )

    def decide_edge(
        self,
        record: HandoffRecord,
        coeff: Coefficients,
        dpsi: float,
        report: StructuralTransitionReport,
        cgt_dict: dict,
    ) -> EdgeDecision:
        p = self.policy
        previous_state = record.state
        new_state = previous_state
        reason = "handoff stable"
        action = MaestroAction.HANDOFF

        rank = self._rank(report)

        if coeff.C >= p.quarantine_policy_risk or coeff.M >= p.quarantine_policy_risk:
            new_state = AgentState.QUARANTINED
            reason = "handoff quarantined: high ambiguity/risk/rework"
            action = MaestroAction.QUARANTINE
        elif rank == ExistenceRank.EXTINCT:
            new_state = AgentState.ARCHIVED
            reason = "handoff extinct: no viable carrier/effect"
            action = MaestroAction.REROUTE
        elif rank == ExistenceRank.DISTORTED and dpsi < 0:
            new_state = AgentState.TRANSITIONAL
            reason = "handoff distorted: add mediator or simplify schema"
            action = MaestroAction.REROUTE
        elif record.psi <= p.archive_max_psi and report.aftermath.balance < p.min_aftermath_balance:
            new_state = AgentState.ARCHIVED
            reason = "handoff archived: structurally harmful edge"
            action = MaestroAction.REROUTE
        elif dpsi < -p.alpha or report.transition_channel >= p.max_transition_channel or record.psi < p.min_edge_psi:
            new_state = AgentState.TRANSITIONAL
            reason = "handoff degraded: add mediator or reroute"
            action = MaestroAction.REROUTE
        elif report.retention >= p.min_retention and report.compatibility >= 0.55:
            new_state = AgentState.ACTIVE
            reason = "handoff healthy"
            action = MaestroAction.HANDOFF
        else:
            reason = "handoff hysteresis: keep observing"
            action = MaestroAction.OBSERVE

        return EdgeDecision(
            edge_id=record.edge_id,
            source_agent_id=record.source_agent_id,
            target_agent_id=record.target_agent_id,
            previous_state=previous_state,
            new_state=new_state,
            psi=record.psi,
            dpsi=dpsi,
            coefficients=coeff,
            reason=reason,
            cgt=cgt_dict,
            action=action,
            confidence=self._confidence(coeff, report),
            policy_version=p.policy_version,
        )

    def decide_workflow(
        self,
        record: WorkflowRecord,
        coeff: Coefficients,
        dpsi: float,
        report: StructuralTransitionReport,
        cgt_dict: dict,
    ) -> WorkflowDecision:
        p = self.policy
        previous_state = record.state
        new_state = previous_state
        reason = "workflow stable"
        action = MaestroAction.OBSERVE
        review = False

        failed = [s for s in record.steps.values() if s.state.value == "failed"]
        pending = [s for s in record.steps.values() if s.state.value == "pending"]
        running = [s for s in record.steps.values() if s.state.value == "running"]
        completed = [s for s in record.steps.values() if s.state.value == "completed"]

        rank = self._rank(report)

        if coeff.M >= p.quarantine_policy_risk or coeff.C >= p.quarantine_policy_risk:
            new_state = WorkflowState.ESCALATED
            reason = "workflow risk too high: human review required"
            action = MaestroAction.ESCALATE
            review = True
        elif len(completed) == len(record.steps) and record.steps:
            new_state = WorkflowState.COMPLETED
            reason = "all workflow steps completed"
            action = MaestroAction.FINALIZE
        elif rank == ExistenceRank.EXTINCT and record.steps:
            new_state = WorkflowState.DEGRADED
            reason = "workflow extinct: no viable carrier/effect"
            action = MaestroAction.REROUTE
        elif rank == ExistenceRank.DISTORTED and dpsi < 0:
            new_state = WorkflowState.DEGRADED
            reason = "workflow distorted: reduce complexity before continuation"
            action = MaestroAction.REROUTE
        elif failed and all(s.attempts >= min(s.step.max_retries, p.max_step_attempts) for s in failed):
            new_state = WorkflowState.DEGRADED
            reason = "workflow degraded: failed steps exhausted retries"
            action = MaestroAction.REROUTE
        elif (
            dpsi < -p.alpha or record.psi < p.min_workflow_psi or report.transition_channel >= p.max_transition_channel
        ):
            new_state = WorkflowState.DEGRADED
            reason = "workflow vitality decaying: reroute or parallelize"
            action = MaestroAction.REROUTE
        elif pending or running:
            new_state = WorkflowState.RUNNING
            reason = "workflow in progress"
            action = MaestroAction.DELEGATE
        else:
            new_state = WorkflowState.PAUSED
            reason = "no executable work found"
            action = MaestroAction.PAUSE

        return WorkflowDecision(
            workflow_id=record.plan.workflow_id,
            previous_state=previous_state,
            new_state=new_state,
            psi=record.psi,
            dpsi=dpsi,
            coefficients=coeff,
            reason=reason,
            action=action,
            cgt=cgt_dict,
            requires_human_review=review,
            confidence=self._confidence(coeff, report),
            policy_version=p.policy_version,
        )
