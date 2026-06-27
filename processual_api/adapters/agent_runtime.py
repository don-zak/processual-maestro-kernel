"""Agent Runtime Adapter — universal interface for any agent framework.

Usage:
    class MyCustomRuntime(RuntimeAdapter):
        ...

    RuntimeAdapterRegistry.register("my-framework", MyCustomRuntime())
    adapter = RuntimeAdapterRegistry.get("my-framework")
    result = await adapter.run_agent("agent-1", {"task": "..."})
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentExecutionResult:
    agent_id: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    telemetry: dict[str, float] = field(default_factory=dict)


@dataclass
class RuntimeHealth:
    available: bool
    framework: str
    version: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


class RuntimeAdapter(ABC):
    @property
    @abstractmethod
    def framework_name(self) -> str:
        ...

    @abstractmethod
    async def run_agent(self, agent_id: str, task: dict[str, Any], **kwargs) -> AgentExecutionResult:
        ...

    @abstractmethod
    async def check_health(self) -> RuntimeHealth:
        ...

    async def list_agents(self) -> list[dict[str, Any]]:
        return []

    async def stop_agent(self, agent_id: str) -> bool:
        return False


class RuntimeAdapterRegistry:
    def __init__(self):
        self._adapters: dict[str, RuntimeAdapter] = {}

    def register(self, name: str, adapter: RuntimeAdapter) -> None:
        self._adapters[name.lower()] = adapter

    def get(self, name: str) -> RuntimeAdapter | None:
        return self._adapters.get(name.lower())

    def all(self) -> dict[str, RuntimeAdapter]:
        return dict(self._adapters)

    def list(self) -> list[dict[str, Any]]:
        return [
            {"name": name, "framework": a.framework_name, "health": None}
            for name, a in self._adapters.items()
        ]


runtime_registry = RuntimeAdapterRegistry()
