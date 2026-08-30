"""Stable, runtime-agnostic enum contracts for Processual Maestro Kernel."""

from __future__ import annotations

from enum import StrEnum


class AgentState(StrEnum):
    ACTIVE = "active"
    TRANSITIONAL = "transitional"
    ARCHIVED = "archived"
    QUARANTINED = "quarantined"


class AgentCriticality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowState(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class StepState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class MaestroAction(StrEnum):
    DELEGATE = "delegate"
    HANDOFF = "handoff"
    PARALLELIZE = "parallelize"
    RETRY = "retry"
    REROUTE = "reroute"
    MERGE = "merge"
    PAUSE = "pause"
    QUARANTINE = "quarantine"
    ARCHIVE = "archive"
    REACTIVATE = "reactivate"
    ESCALATE = "escalate"
    FINALIZE = "finalize"
    OBSERVE = "observe"
