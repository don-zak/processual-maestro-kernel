from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


def _new_decision_id() -> str:
    return f"dec_{uuid.uuid4().hex}"


class AgentState(str, Enum):
    ACTIVE = "active"
    TRANSITIONAL = "transitional"
    ARCHIVED = "archived"
    QUARANTINED = "quarantined"


class AgentCriticality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowState(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class StepState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class MaestroAction(str, Enum):
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


@dataclass(frozen=True, slots=True)
class AgentSpec:
    agent_id: str
    role: str
    version: str = "0.2.0"
    capabilities: tuple[str, ...] = ()
    criticality: AgentCriticality = AgentCriticality.MEDIUM
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentTelemetry:
    """Telemetry for a single agent observation.

    Most values are normalized to [0, 1]. Raw fields such as latency and age are mapped by the coefficient mapper.
    """

    success_rate: float = 1.0
    cooperation_success: float = 0.5
    useful_handoff_rate: float = 0.5
    demand_rate: float = 0.0
    business_priority: float = 0.5
    resource_cost: float = 0.0
    overlap_score: float = 0.0
    policy_risk: float = 0.0
    failure_count: int = 0
    age_seconds: float = 0.0
    latency_p95_ms: float = 0.0
    queue_depth: float = 0.0
    custom: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class HandoffTelemetry:
    """Telemetry for the edge between two agents or workflow steps."""

    artifact_quality: float = 0.5
    context_preservation: float = 0.5
    acceptance_rate: float = 0.5
    rework_rate: float = 0.0
    latency_ms: float = 0.0
    ambiguity: float = 0.0
    policy_risk: float = 0.0
    demand_rate: float = 0.5
    custom: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowTelemetry:
    """Telemetry for the whole workflow, not just one agent or one handoff."""

    goal_alignment: float = 0.5
    progress_rate: float = 0.0
    completion_confidence: float = 0.0
    coordination_quality: float = 0.5
    blocking_rate: float = 0.0
    rework_rate: float = 0.0
    cost_pressure: float = 0.0
    latency_pressure: float = 0.0
    risk_pressure: float = 0.0
    demand_rate: float = 0.5
    custom: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Coefficients:
    T: float
    N: float
    C: float
    M: float


@dataclass(slots=True)
class AgentRecord:
    spec: AgentSpec
    state: AgentState = AgentState.ACTIVE
    psi: float = 0.0
    previous_psi: float = 0.0
    last_coefficients: Coefficients | None = None
    last_updated_at: float = field(default_factory=time.time)
    failure_streak: int = 0
    observations: int = 0


@dataclass(slots=True)
class HandoffRecord:
    source_agent_id: str
    target_agent_id: str
    state: AgentState = AgentState.ACTIVE
    psi: float = 0.0
    previous_psi: float = 0.0
    last_coefficients: Coefficients | None = None
    observations: int = 0
    last_updated_at: float = field(default_factory=time.time)

    @property
    def edge_id(self) -> str:
        return f"{self.source_agent_id}->{self.target_agent_id}"


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    step_id: str
    capability: str
    instruction: str
    depends_on: tuple[str, ...] = ()
    preferred_agent_id: str | None = None
    parallel_group: str | None = None
    max_retries: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkflowPlan:
    workflow_id: str
    goal: str
    steps: tuple[WorkflowStep, ...]
    priority: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StepRecord:
    step: WorkflowStep
    state: StepState = StepState.PENDING
    assigned_agent_id: str | None = None
    attempts: int = 0
    output: Any = None
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None


@dataclass(slots=True)
class WorkflowRecord:
    plan: WorkflowPlan
    state: WorkflowState = WorkflowState.DRAFT
    psi: float = 0.0
    previous_psi: float = 0.0
    last_coefficients: Coefficients | None = None
    steps: dict[str, StepRecord] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class KernelPolicy:
    policy_version: str = "core-0.3.0"
    dt: float = 1.0
    alpha: float = 0.05
    active_min_psi: float = 0.20
    archive_max_psi: float = -0.10
    reactivation_need: float = 0.72
    min_retention: float = 0.12
    max_transition_channel: float = 0.78
    min_aftermath_balance: float = -0.05
    quarantine_policy_risk: float = 0.85
    critical_requires_review: bool = True
    max_failure_streak: int = 3
    min_edge_psi: float = -0.04
    min_workflow_psi: float = -0.02
    max_step_attempts: int = 2
    prefer_high_psi_agents: bool = True


@dataclass(frozen=True, slots=True)
class GovernanceDecision:
    agent_id: str
    previous_state: AgentState
    new_state: AgentState
    psi: float
    dpsi: float
    coefficients: Coefficients
    reason: str
    cgt: dict[str, Any]
    requires_human_review: bool = False
    confidence: float = 0.0
    policy_version: str = "unversioned"
    decision_id: str = field(default_factory=_new_decision_id)
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class EdgeDecision:
    edge_id: str
    source_agent_id: str
    target_agent_id: str
    previous_state: AgentState
    new_state: AgentState
    psi: float
    dpsi: float
    coefficients: Coefficients
    reason: str
    cgt: dict[str, Any]
    action: MaestroAction = MaestroAction.HANDOFF
    confidence: float = 0.0
    policy_version: str = "unversioned"
    decision_id: str = field(default_factory=_new_decision_id)
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class WorkflowDecision:
    workflow_id: str
    previous_state: WorkflowState
    new_state: WorkflowState
    psi: float
    dpsi: float
    coefficients: Coefficients
    reason: str
    action: MaestroAction
    cgt: dict[str, Any]
    requires_human_review: bool = False
    confidence: float = 0.0
    policy_version: str = "unversioned"
    decision_id: str = field(default_factory=_new_decision_id)
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class MaestroEvent:
    workflow_id: str | None
    action: MaestroAction
    subject: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class TaskEnvelope:
    task_id: str
    required_capability: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: float = 0.5


@dataclass(frozen=True, slots=True)
class TaskResult:
    task_id: str
    agent_id: str
    ok: bool
    output: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    cost: float = 0.0


class AgentRuntime(Protocol):
    async def run(self, agent: AgentSpec, task: TaskEnvelope) -> TaskResult: ...


class AuditSink(Protocol):
    def write(self, event: Any) -> None: ...
