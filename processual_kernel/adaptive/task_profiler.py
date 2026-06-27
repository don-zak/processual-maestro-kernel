from __future__ import annotations

from typing import Any

from ..adaptive_types import AgentCountBand, AmbiguityLevel, RiskLevel, TaskDuration, TaskProfile, TaskSize
from ..types import WorkflowPlan, WorkflowRecord


def _enum_value(enum_cls, value: Any, default):
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower().replace("_", "-")
        for item in enum_cls:
            if item.value == normalized:
                return item
    return default


class TaskProfiler:
    """Infers a workflow profile before adaptive policy selection.

    The profiler reads workflow metadata first and only falls back to simple size heuristics.
    It does not alter the core kernel state.
    """

    def profile(self, workflow: WorkflowPlan | WorkflowRecord) -> TaskProfile:
        plan = workflow.plan if isinstance(workflow, WorkflowRecord) else workflow
        metadata = dict(plan.metadata or {})
        step_count = len(plan.steps)
        estimated_minutes = metadata.get("estimated_minutes")
        try:
            estimated_minutes = int(estimated_minutes) if estimated_minutes is not None else None
        except (TypeError, ValueError):
            estimated_minutes = None

        size = _enum_value(TaskSize, metadata.get("size"), self._size_from_steps(step_count))
        duration = _enum_value(
            TaskDuration, metadata.get("duration"), self._duration_from_estimate(step_count, estimated_minutes)
        )
        risk = _enum_value(RiskLevel, metadata.get("risk"), self._risk_from_metadata(metadata))
        ambiguity = _enum_value(AmbiguityLevel, metadata.get("ambiguity"), self._ambiguity_from_metadata(metadata))
        agent_count = _enum_value(AgentCountBand, metadata.get("agent_count"), self._agent_count_from_plan(plan))
        budget_sensitivity = _enum_value(RiskLevel, metadata.get("budget_sensitivity"), RiskLevel.MEDIUM)

        requires_hourly = bool(duration == TaskDuration.LONG)
        requires_audit = bool(metadata.get("requires_audit", True)) or risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        return TaskProfile(
            size=size,
            duration=duration,
            risk=risk,
            ambiguity=ambiguity,
            agent_count=agent_count,
            requires_hourly_checkpoint=requires_hourly,
            requires_audit=requires_audit,
            budget_sensitivity=budget_sensitivity,
            estimated_minutes=estimated_minutes,
            metadata=metadata,
        )

    @staticmethod
    def _size_from_steps(step_count: int) -> TaskSize:
        if step_count <= 3:
            return TaskSize.SMALL
        if step_count <= 8:
            return TaskSize.MEDIUM
        return TaskSize.LARGE

    @staticmethod
    def _duration_from_estimate(step_count: int, estimated_minutes: int | None) -> TaskDuration:
        if estimated_minutes is not None:
            if estimated_minutes >= 60:
                return TaskDuration.LONG
            if estimated_minutes >= 20:
                return TaskDuration.MEDIUM
            return TaskDuration.SHORT
        if step_count >= 9:
            return TaskDuration.LONG
        if step_count >= 4:
            return TaskDuration.MEDIUM
        return TaskDuration.SHORT

    @staticmethod
    def _risk_from_metadata(metadata: dict[str, Any]) -> RiskLevel:
        if metadata.get("critical") or metadata.get("safety_critical"):
            return RiskLevel.CRITICAL
        if metadata.get("human_approval_required") or metadata.get("sensitive"):
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM

    @staticmethod
    def _ambiguity_from_metadata(metadata: dict[str, Any]) -> AmbiguityLevel:
        score = metadata.get("ambiguity_score")
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = None
        if score is not None:
            if score >= 0.67:
                return AmbiguityLevel.HIGH
            if score >= 0.34:
                return AmbiguityLevel.MEDIUM
            return AmbiguityLevel.LOW
        if metadata.get("exploratory") or metadata.get("research"):
            return AmbiguityLevel.HIGH
        return AmbiguityLevel.MEDIUM

    @staticmethod
    def _agent_count_from_plan(plan: WorkflowPlan) -> AgentCountBand:
        preferred = {s.preferred_agent_id for s in plan.steps if s.preferred_agent_id}
        count = len(preferred) if preferred else len(plan.steps)
        if count <= 1:
            return AgentCountBand.SINGLE
        if count <= 4:
            return AgentCountBand.FEW
        return AgentCountBand.MANY
