from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TaskEnvelope:
    task_id: str
    required_capability: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: float = 0.5

    __module__ = "processual_kernel.types"


@dataclass(frozen=True, slots=True)
class TaskResult:
    task_id: str
    agent_id: str
    ok: bool
    output: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    cost: float = 0.0

    __module__ = "processual_kernel.types"
