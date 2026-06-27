"""CGT Governor Gateway — Storage Backends

Abstract storage interface + in-memory + JSON-file backends
for persisting agent registry data across server restarts.

Usage:
    storage = create_storage()  # auto-detect from CGT_GATEWAY_STORAGE env
    registry = AgentRegistry(storage=storage)
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .models import Agent, AgentState, EvaluationRecord, GatewayAction

logger = logging.getLogger("processual_api.cgt_governor.gateway.storage")

try:
    import orjson

    def _dumps(obj: Any) -> str:
        return orjson.dumps(obj, option=orjson.OPT_APPEND_NEWLINE).decode()

    def _loads(data: str) -> Any:
        return orjson.loads(data)

except ImportError:

    def _dumps(obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"

    def _loads(data: str) -> Any:
        return json.loads(data)


class GatewayStorage(ABC):
    """Abstract storage backend for the AgentRegistry."""

    @abstractmethod
    def load_agents(self) -> list[dict]:
        """Load all stored agents as plain dicts."""

    @abstractmethod
    def save_agents(self, agents: list[dict]) -> None:
        """Persist all agents."""

    @abstractmethod
    def close(self) -> None:
        """Release any resources (file handles, connections)."""


class MemoryStorage(GatewayStorage):
    """In-memory only — no persistence."""

    def load_agents(self) -> list[dict]:
        return []

    def save_agents(self, agents: list[dict]) -> None:
        pass

    def close(self) -> None:
        pass


class JSONFileStorage(GatewayStorage):
    """Persist agents to a JSON file (one array per file).

    File format: [{agent_dict}, ...] (pretty-printed JSON).
    """

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._lock = False  # simple flag guard against concurrent save/load
        logger.info("JSONFileStorage path: %s", self._path)

    def load_agents(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = _loads(raw)
            if isinstance(data, list):
                return data
            logger.warning("Unexpected data format in %s, resetting", self._path)
            return []
        except (json.JSONDecodeError, OSError, Exception) as exc:
            logger.error("Failed to load storage %s: %s", self._path, exc)
            return []

    def save_agents(self, agents: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._path.write_text(_dumps(agents), encoding="utf-8")
        except OSError as exc:
            logger.error("Failed to save storage %s: %s", self._path, exc)

    def close(self) -> None:
        pass


def _agent_to_dict(agent: Agent) -> dict:
    """Convert an Agent dataclass to a JSON-safe dict."""
    base = dataclasses.asdict(agent)
    base["state"] = agent.state.value
    base["evaluation_history"] = [
        {
            "timestamp": e.timestamp,
            "client_query": e.client_query,
            "agent_response": e.agent_response,
            "rank": e.rank,
            "reward": e.reward,
            "policy": e.policy,
            "policy_label": e.policy_label,
            "fate_vector": dict(e.fate_vector),
            "repair_prompt": e.repair_prompt,
            "action_taken": e.action_taken.value,
            "language": e.language,
        }
        for e in agent.evaluation_history
    ]
    return base


def _dict_to_agent(data: dict) -> Agent:
    """Rebuild an Agent dataclass from a dict."""
    state_str = data.pop("state", "active")
    state = AgentState(state_str)

    evals_raw = data.pop("evaluation_history", [])
    evals = []
    for e in evals_raw:
        action_str = e.pop("action_taken", "pass")
        evals.append(
            EvaluationRecord(
                timestamp=e.get("timestamp", ""),
                client_query=e.get("client_query", ""),
                agent_response=e.get("agent_response", ""),
                rank=e.get("rank", ""),
                reward=float(e.get("reward", 0)),
                policy=e.get("policy", ""),
                policy_label=e.get("policy_label", ""),
                fate_vector=dict(e.get("fate_vector", {})),
                repair_prompt=e.get("repair_prompt"),
                action_taken=GatewayAction(action_str),
                language=e.get("language", "en"),
            )
        )

    pw = [float(r) for r in data.pop("performance_window", [])]
    agent = Agent(
        agent_id=str(data.get("agent_id", "")),
        name=str(data.get("name", "")),
        role=str(data.get("role", "")),
        adapter_name=str(data.get("adapter_name", "")),
        model=str(data.get("model", "")),
        system_prompt=str(data.get("system_prompt", "")),
        language=str(data.get("language", "en")),
        state=state,
        created_at=str(data.get("created_at", "")),
        last_state_change=str(data.get("last_state_change", "")),
        last_state_reason=str(data.get("last_state_reason", "")),
        tags=list(data.get("tags", [])),
        priority=int(data.get("priority", 1)),
        risk_level=str(data.get("risk_level", "medium")),
        owner=str(data.get("owner", "")),
        policy_profile=str(data.get("policy_profile", "default")),
    )
    agent.evaluation_history = evals
    agent.performance_window = pw
    agent.consecutive_failures = int(data.get("consecutive_failures", 0))
    return agent


def _default_storage_path() -> Path:
    """Return a persistent path inside the project's data directory."""
    base = Path(__file__).resolve().parent.parent.parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base / "gateway_agents.json"


def create_storage() -> GatewayStorage:
    """Create a storage backend based on environment configuration.

    - CGT_GATEWAY_STORAGE=memory        → MemoryStorage
    - CGT_GATEWAY_STORAGE=json          → JSONFileStorage (default)
    - CGT_GATEWAY_STORAGE_PATH=<path>   → JSON file path (default: data/gateway_agents.json)
    """
    kind = os.environ.get("CGT_GATEWAY_STORAGE", "json").lower()
    if kind == "memory":
        return MemoryStorage()
    path = os.environ.get(
        "CGT_GATEWAY_STORAGE_PATH",
        str(_default_storage_path()),
    )
    return JSONFileStorage(path)
