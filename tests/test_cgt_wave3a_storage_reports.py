from __future__ import annotations

import json

import pytest

from processual_api.cgt_governor.gateway.models import (
    Agent,
    AgentState,
    EvaluationRecord,
    GatewayAction,
)
from processual_api.cgt_governor.gateway.storage import (
    JSONFileStorage,
    MemoryStorage,
    _agent_to_dict,
    _dict_to_agent,
    create_storage,
)
from processual_api.cgt_governor.simulation.agents import AgentPersona
from processual_api.cgt_governor.simulation.engine import (
    AgentEvaluation,
    SimulationResult,
)
from processual_api.cgt_governor.simulation.reports import (
    generate_supervision_pdf,
)


def _gateway_agent() -> Agent:
    agent = Agent(
        agent_id="agent-1",
        name="Coverage Agent",
        role="tester",
        adapter_name="fake",
        model="test-model",
        system_prompt="test",
        language="en",
        state=AgentState.ACTIVE,
        created_at="2026-08-12T00:00:00Z",
        last_state_change="2026-08-12T00:00:00Z",
        last_state_reason="created",
        tags=["coverage"],
        priority=3,
        risk_level="low",
        owner="qa",
        policy_profile="strict",
    )

    agent.evaluation_history = [
        EvaluationRecord(
            timestamp="2026-08-12T00:01:00Z",
            client_query="question",
            agent_response="answer",
            rank="stable",
            reward=0.75,
            policy="allow",
            policy_label="Allowed",
            fate_vector={
                "stability": 0.8,
                "distortion": 0.1,
            },
            repair_prompt=None,
            action_taken=GatewayAction.PASS,
            language="en",
        ),
        EvaluationRecord(
            timestamp="2026-08-12T00:02:00Z",
            client_query="bad question",
            agent_response="bad answer",
            rank="distorted",
            reward=-0.25,
            policy="repair",
            policy_label="Needs repair",
            fate_vector={
                "stability": 0.2,
                "distortion": 0.7,
            },
            repair_prompt="Rewrite safely",
            action_taken=GatewayAction.REPAIR,
            language="ar",
        ),
    ]

    agent.performance_window = [0.2, 0.5, 0.9]
    agent.consecutive_failures = 2
    return agent


def test_memory_storage_is_noop():
    storage = MemoryStorage()

    assert storage.load_agents() == []
    assert storage.save_agents([{"agent_id": "x"}]) is None
    assert storage.close() is None


def test_json_storage_missing_file_and_roundtrip(tmp_path):
    path = tmp_path / "nested" / "agents.json"
    storage = JSONFileStorage(path)

    assert storage.load_agents() == []

    payload = [
        {
            "agent_id": "a1",
            "state": "active",
        }
    ]

    storage.save_agents(payload)

    assert path.exists()
    assert storage.load_agents() == payload
    assert storage.close() is None


def test_json_storage_rejects_non_list_payload(tmp_path):
    path = tmp_path / "agents.json"
    path.write_text(
        json.dumps({"agent_id": "not-a-list"}),
        encoding="utf-8",
    )

    storage = JSONFileStorage(path)

    assert storage.load_agents() == []


def test_json_storage_handles_invalid_json(tmp_path):
    path = tmp_path / "agents.json"
    path.write_text("{ invalid json", encoding="utf-8")

    storage = JSONFileStorage(path)

    assert storage.load_agents() == []


def test_json_storage_handles_read_error(tmp_path, monkeypatch):
    path = tmp_path / "agents.json"
    path.write_text("[]", encoding="utf-8")

    storage = JSONFileStorage(path)

    def fail_read(*args, **kwargs):
        raise OSError("read failed")

    monkeypatch.setattr(type(path), "read_text", fail_read)

    assert storage.load_agents() == []


def test_json_storage_handles_write_error(tmp_path, monkeypatch):
    path = tmp_path / "agents.json"
    storage = JSONFileStorage(path)

    def fail_write(*args, **kwargs):
        raise OSError("write failed")

    monkeypatch.setattr(type(path), "write_text", fail_write)

    assert storage.save_agents([]) is None


def test_agent_serialization_roundtrip():
    original = _gateway_agent()

    data = _agent_to_dict(original)

    assert data["state"] == "active"
    assert data["evaluation_history"][0]["action_taken"] == "pass"
    assert data["evaluation_history"][1]["action_taken"] == "repair"

    rebuilt = _dict_to_agent(dict(data))

    assert rebuilt.agent_id == original.agent_id
    assert rebuilt.name == original.name
    assert rebuilt.state == AgentState.ACTIVE
    assert rebuilt.performance_window == [0.2, 0.5, 0.9]
    assert rebuilt.consecutive_failures == 2
    assert len(rebuilt.evaluation_history) == 2

    first = rebuilt.evaluation_history[0]
    second = rebuilt.evaluation_history[1]

    assert first.action_taken == GatewayAction.PASS
    assert first.language == "en"
    assert second.action_taken == GatewayAction.REPAIR
    assert second.repair_prompt == "Rewrite safely"
    assert second.language == "ar"


def test_dict_to_agent_defaults():
    agent = _dict_to_agent(
        {
            "agent_id": "minimal",
            "name": "Minimal",
            "role": "test",
            "adapter_name": "fake",
            "model": "m",
            "system_prompt": "",
            "language": "en",
        }
    )

    assert agent.state == AgentState.ACTIVE
    assert agent.evaluation_history == []
    assert agent.performance_window == []
    assert agent.priority == 1
    assert agent.risk_level == "medium"
    assert agent.policy_profile == "default"


def test_create_storage_memory(monkeypatch):
    monkeypatch.setenv(
        "CGT_GATEWAY_STORAGE",
        "memory",
    )

    storage = create_storage()

    assert isinstance(storage, MemoryStorage)


def test_create_storage_json_with_explicit_path(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "custom.json"

    monkeypatch.setenv(
        "CGT_GATEWAY_STORAGE",
        "json",
    )
    monkeypatch.setenv(
        "CGT_GATEWAY_STORAGE_PATH",
        str(path),
    )

    storage = create_storage()

    assert isinstance(storage, JSONFileStorage)
    assert storage._path == path


def _persona(
    *,
    agent_id: str,
    name: str,
    role: str = "Tester",
) -> AgentPersona:
    return AgentPersona(
        agent_id=agent_id,
        name=name,
        role=role,
        language="en",
        description="coverage persona",
        quality="high",
    )


def _evaluation(
    *,
    agent: AgentPersona,
    rank: str,
    reward: float,
    repair_prompt: str | None = None,
) -> AgentEvaluation:
    return AgentEvaluation(
        agent=agent,
        scenario_title="Coverage scenario",
        rank=rank,
        reward=reward,
        policy="allow",
        policy_label="Allowed",
        fate_vector={
            "stability": 0.8,
            "distortion": 0.1,
            "extinction": 0.05,
            "flourishing": 0.7,
        },
        repair_prompt=repair_prompt,
    )


def test_generate_supervision_pdf_stable_report():
    agent = _persona(
        agent_id="stable-agent",
        name="Stable Agent",
    )

    report = SimulationResult(
        simulation_id="sim-1",
        ts="2026-08-12T00:00:00Z",
        evaluations=[
            _evaluation(
                agent=agent,
                rank="stable",
                reward=0.8,
            ),
        ],
        rank_distribution={
            "stable": 1,
        },
        avg_reward=0.8,
        highest_agent=None,
        lowest_agent=None,
        risk_count=0,
    )

    pdf = generate_supervision_pdf(report)

    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500


def test_generate_supervision_pdf_risk_repair_and_signature(
    monkeypatch,
):
    best = _persona(
        agent_id="best",
        name="Best Agent",
    )
    worst = _persona(
        agent_id="worst",
        name="Worst Agent",
    )

    evaluations = [
        _evaluation(
            agent=best,
            rank="flourishing",
            reward=0.9,
        ),
        _evaluation(
            agent=worst,
            rank="distorted",
            reward=-0.5,
            repair_prompt="Repair this response",
        ),
    ]

    report = SimulationResult(
        simulation_id="sim-2",
        ts="2026-08-12T00:00:00Z",
        evaluations=evaluations,
        rank_distribution={
            "flourishing": 1,
            "distorted": 1,
        },
        avg_reward=0.2,
        highest_agent="best",
        lowest_agent="worst",
        risk_count=1,
    )

    monkeypatch.setattr(
        "processual_api.cgt_governor.simulation.reports.ALL_AGENTS",
        [best, worst],
    )

    pdf = generate_supervision_pdf(
        report,
        signature="abc123",
    )

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500


@pytest.mark.parametrize(
    "rank",
    [
        "hybrid",
        "transient",
        "extinct",
        "unknown-rank",
    ],
)
def test_generate_supervision_pdf_rank_variants(
    rank,
):
    agent = _persona(
        agent_id=f"agent-{rank}",
        name="Rank Agent",
    )

    report = SimulationResult(
        simulation_id="sim-rank",
        ts="2026-08-12T00:00:00Z",
        evaluations=[
            _evaluation(
                agent=agent,
                rank=rank,
                reward=0.0,
            ),
        ],
        rank_distribution={
            rank: 1,
        },
        avg_reward=0.0,
        highest_agent=None,
        lowest_agent=None,
        risk_count=1 if rank == "extinct" else 0,
    )

    pdf = generate_supervision_pdf(report)

    assert pdf.startswith(b"%PDF")

def test_storage_falls_back_without_orjson(monkeypatch):
    import builtins
    import importlib

    import processual_api.cgt_governor.gateway.storage as storage_module

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "orjson":
            raise ImportError("forced missing orjson")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    reloaded = importlib.reload(storage_module)

    try:
        encoded = reloaded._dumps([{"name": "مرحبا"}])

        assert encoded.endswith("\n")
        assert reloaded._loads(encoded) == [{"name": "مرحبا"}]
    finally:
        monkeypatch.setattr(builtins, "__import__", original_import)
        importlib.reload(storage_module)
