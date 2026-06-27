from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from ..adaptive_types import CheckpointKind, CheckpointReport, PolicyProfile, RiskLevel, TaskDuration, TaskProfile
from ..types import AgentState, MaestroAction, StepState, WorkflowRecord, WorkflowState

RISK_EVENTS = {
    "repeated_failure",
    "high_cost_spike",
    "handoff_degradation",
    "workflow_loop",
    "critical_agent_failure",
    "human_escalation",
}


class CheckpointScheduler:
    """Produces time-, event-, milestone-, and final-checkpoint reports."""

    def __init__(self):
        self._last_checkpoint_at: dict[str, float] = {}
        self._counter: dict[str, int] = defaultdict(int)

    def maybe_checkpoint(
        self,
        kernel: Any,
        workflow_id: str,
        profile: TaskProfile,
        policy: PolicyProfile,
        event: str | None = None,
        milestone: bool = False,
        final: bool = False,
        now: float | None = None,
    ) -> CheckpointReport | None:
        now = time.time() if now is None else now
        kind = self._checkpoint_kind(workflow_id, profile, policy, event, milestone, final, now)
        if kind is None:
            return None
        report = self.build_report(kernel, workflow_id, profile, policy, kind, now)
        self._last_checkpoint_at[workflow_id] = now
        return report

    def build_report(
        self,
        kernel: Any,
        workflow_id: str,
        profile: TaskProfile,
        policy: PolicyProfile,
        kind: CheckpointKind,
        now: float | None = None,
    ) -> CheckpointReport:
        workflow = kernel.get_workflow(workflow_id)
        self._counter[workflow_id] += 1
        workflow_status = self._workflow_status(workflow)
        agent_findings = self._agent_findings(kernel, workflow)
        handoff_findings = self._handoff_findings(kernel, workflow)
        risks = self._risks(workflow, agent_findings, handoff_findings, profile)
        action = self._recommended_action(workflow, risks, profile)
        confidence = self._confidence(workflow_status, risks)
        return CheckpointReport(
            workflow_id=workflow_id,
            kind=kind,
            checkpoint_number=self._counter[workflow_id],
            policy_name=policy.name,
            policy_version=policy.policy_version,
            workflow_status=workflow_status,
            agent_findings=agent_findings,
            handoff_findings=handoff_findings,
            risks=tuple(risks),
            recommended_action=action,
            confidence=confidence,
            created_at=time.time() if now is None else now,
        )

    def _checkpoint_kind(
        self,
        workflow_id: str,
        profile: TaskProfile,
        policy: PolicyProfile,
        event: str | None,
        milestone: bool,
        final: bool,
        now: float,
    ) -> CheckpointKind | None:
        if final:
            return CheckpointKind.FINAL
        if event in RISK_EVENTS:
            return CheckpointKind.EVENT_BASED
        if milestone:
            return CheckpointKind.MILESTONE
        interval = policy.checkpoint_interval_minutes
        if interval is None:
            return None
        last = self._last_checkpoint_at.get(workflow_id)
        if last is None:
            return CheckpointKind.HOURLY if profile.duration == TaskDuration.LONG else CheckpointKind.MILESTONE
        if now - last >= interval * 60:
            return CheckpointKind.HOURLY if interval >= 60 else CheckpointKind.MILESTONE
        return None

    @staticmethod
    def _workflow_status(workflow: WorkflowRecord) -> dict[str, Any]:
        total = max(1, len(workflow.steps))
        completed = sum(1 for s in workflow.steps.values() if s.state == StepState.COMPLETED)
        failed = sum(1 for s in workflow.steps.values() if s.state == StepState.FAILED)
        running = sum(1 for s in workflow.steps.values() if s.state == StepState.RUNNING)
        return {
            "workflow_state": workflow.state.value,
            "workflow_psi": workflow.psi,
            "workflow_trend": workflow.psi - workflow.previous_psi,
            "completion_progress": completed / total,
            "failed_steps": failed,
            "running_steps": running,
            "step_count": len(workflow.steps),
        }

    @staticmethod
    def _agent_findings(kernel: Any, workflow: WorkflowRecord) -> dict[str, Any]:
        agent_ids = {s.assigned_agent_id for s in workflow.steps.values() if s.assigned_agent_id}
        findings: dict[str, Any] = {}
        for agent_id in sorted(agent_ids):
            record = kernel.registry.get(agent_id)
            if record is None:
                continue
            trend = record.psi - record.previous_psi
            status = (
                "degraded"
                if record.state in (AgentState.TRANSITIONAL, AgentState.QUARANTINED) or trend < -0.05
                else "stable"
            )
            findings[agent_id] = {
                "state": record.state.value,
                "psi": record.psi,
                "trend": trend,
                "failure_streak": record.failure_streak,
                "status": status,
            }
        return findings

    @staticmethod
    def _handoff_findings(kernel: Any, workflow: WorkflowRecord) -> dict[str, Any]:
        active_agents = {s.assigned_agent_id for s in workflow.steps.values() if s.assigned_agent_id}
        findings: dict[str, Any] = {}
        for edge_id, record in kernel.handoffs.items():
            if record.source_agent_id not in active_agents and record.target_agent_id not in active_agents:
                continue
            trend = record.psi - record.previous_psi
            status = (
                "weak"
                if record.state in (AgentState.TRANSITIONAL, AgentState.QUARANTINED) or record.psi < 0
                else "stable"
            )
            findings[edge_id] = {
                "state": record.state.value,
                "psi": record.psi,
                "trend": trend,
                "observations": record.observations,
                "status": status,
            }
        return findings

    @staticmethod
    def _risks(
        workflow: WorkflowRecord, agents: dict[str, Any], handoffs: dict[str, Any], profile: TaskProfile
    ) -> list[str]:
        risks: list[str] = []
        failed = [sid for sid, s in workflow.steps.items() if s.state == StepState.FAILED]
        if failed:
            risks.append("failed_steps:" + ",".join(failed))
        degraded_agents = [a for a, f in agents.items() if f["status"] == "degraded"]
        if degraded_agents:
            risks.append("degraded_agents:" + ",".join(degraded_agents))
        weak_handoffs = [e for e, f in handoffs.items() if f["status"] == "weak"]
        if weak_handoffs:
            risks.append("weak_handoffs:" + ",".join(weak_handoffs))
        if profile.risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            risks.append("profile_risk:" + profile.risk.value)
        if workflow.state in (WorkflowState.DEGRADED, WorkflowState.ESCALATED, WorkflowState.FAILED):
            risks.append("workflow_state:" + workflow.state.value)
        return risks

    @staticmethod
    def _recommended_action(workflow: WorkflowRecord, risks: list[str], profile: TaskProfile) -> MaestroAction:
        if profile.risk == RiskLevel.CRITICAL and risks:
            return MaestroAction.ESCALATE
        if any(r.startswith("failed_steps") or r.startswith("weak_handoffs") for r in risks):
            return MaestroAction.REROUTE
        if workflow.state == WorkflowState.COMPLETED:
            return MaestroAction.FINALIZE
        if workflow.state == WorkflowState.PAUSED:
            return MaestroAction.PAUSE
        return MaestroAction.OBSERVE

    @staticmethod
    def _confidence(workflow_status: dict[str, Any], risks: list[str]) -> float:
        base = 0.85
        base += min(0.10, workflow_status.get("completion_progress", 0.0) * 0.10)
        base -= min(0.45, 0.08 * len(risks))
        return round(max(0.0, min(1.0, base)), 4)
