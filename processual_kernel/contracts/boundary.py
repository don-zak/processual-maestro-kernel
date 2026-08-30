from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from .enums import AgentCriticality, MaestroAction
from .tasks import TaskEnvelope, TaskResult


@dataclass(frozen=True, slots=True)
class AgentSpec:
    agent_id: str
    role: str
    version: str = "0.2.0"
    capabilities: tuple[str, ...] = ()
    criticality: AgentCriticality = AgentCriticality.MEDIUM
    metadata: dict[str, Any] = field(default_factory=dict)

    __module__ = "processual_kernel.types"


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

    __module__ = "processual_kernel.types"


@dataclass(frozen=True, slots=True)
class WorkflowPlan:
    workflow_id: str
    goal: str
    steps: tuple[WorkflowStep, ...]
    priority: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    __module__ = "processual_kernel.types"


@dataclass(frozen=True, slots=True)
class MaestroEvent:
    workflow_id: str | None
    action: MaestroAction
    subject: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    __module__ = "processual_kernel.types"


class AgentRuntime(Protocol):
    async def run(self, agent: AgentSpec, task: TaskEnvelope) -> TaskResult: ...


class AuditSink(Protocol):
    def write(self, event: Any) -> None: ...


AgentRuntime.__module__ = "processual_kernel.types"
AuditSink.__module__ = "processual_kernel.types"
