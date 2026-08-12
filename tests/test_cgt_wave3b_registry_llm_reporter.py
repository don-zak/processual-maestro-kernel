from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest

from processual_api.cgt_governor.gateway.models import (
    Agent,
    AgentState,
    EvaluationRecord,
    GatewayAction,
)
from processual_api.cgt_governor.gateway.registry import AgentRegistry
from processual_api.cgt_governor.reports import llm_reporter


class SpyStorage:
    def __init__(self, initial=None):
        self.initial = list(initial or [])
        self.saved = []

    def load_agents(self):
        return self.initial

    def save_agents(self, agents):
        self.saved.append(agents)

    def close(self):
        return None


def _agent(
    agent_id: str = "agent-1",
    *,
    state: AgentState = AgentState.ACTIVE,
) -> Agent:
    return Agent(
        agent_id=agent_id,
        name=f"Agent {agent_id}",
        role="tester",
        adapter_name="fake",
        model="test-model",
        system_prompt="test",
        language="en",
        state=state,
        created_at="2026-08-12T00:00:00Z",
        last_state_change="2026-08-12T00:00:00Z",
        last_state_reason="created",
    )


def _record(
    *,
    reward: float = 0.5,
    action: GatewayAction = GatewayAction.PASS,
) -> EvaluationRecord:
    return EvaluationRecord(
        timestamp="2026-08-12T00:01:00Z",
        client_query="question",
        agent_response="answer",
        rank="stable",
        reward=reward,
        policy="allow",
        policy_label="Allowed",
        fate_vector={"stability": 0.8},
        repair_prompt=None,
        action_taken=action,
        language="en",
    )


def test_registry_loads_existing_agents_and_lists_by_state():
    existing = _agent("loaded")
    storage = SpyStorage(
        [
            {
                "agent_id": existing.agent_id,
                "name": existing.name,
                "role": existing.role,
                "adapter_name": existing.adapter_name,
                "model": existing.model,
                "system_prompt": existing.system_prompt,
                "language": existing.language,
                "state": existing.state.value,
                "created_at": existing.created_at,
                "last_state_change": existing.last_state_change,
                "last_state_reason": existing.last_state_reason,
            }
        ]
    )

    registry = AgentRegistry(storage=storage)

    assert registry.get("loaded") is not None
    assert [a.agent_id for a in registry.list()] == ["loaded"]
    assert [a.agent_id for a in registry.list(AgentState.ACTIVE)] == ["loaded"]
    assert registry.list(AgentState.FROZEN) == []


def test_registry_register_get_and_persist():
    storage = SpyStorage()
    registry = AgentRegistry(storage=storage)
    agent = _agent()

    result = registry.register(agent)

    assert result == "agent-1"
    assert registry.get("agent-1") is agent
    assert len(storage.saved) == 1
    assert storage.saved[-1][0]["agent_id"] == "agent-1"


def test_registry_change_state_missing_agent():
    registry = AgentRegistry(storage=SpyStorage())

    with pytest.raises(KeyError, match="Agent not found"):
        registry.change_state("missing", AgentState.FROZEN)


def test_registry_change_state_noop_for_same_non_escalated_state():
    storage = SpyStorage()
    registry = AgentRegistry(storage=storage)
    agent = _agent()
    registry.register(agent)
    storage.saved.clear()

    result = registry.change_state(
        agent.agent_id,
        AgentState.ACTIVE,
        "same",
    )

    assert result is agent
    assert storage.saved == []


def test_registry_change_state_updates_and_resets_failures():
    storage = SpyStorage()
    registry = AgentRegistry(storage=storage)
    agent = _agent()
    agent.consecutive_failures = 3
    registry.register(agent)
    storage.saved.clear()

    result = registry.change_state(
        agent.agent_id,
        AgentState.FROZEN,
        "risk",
    )

    assert result.state == AgentState.FROZEN
    assert result.last_state_reason == "risk"
    assert result.consecutive_failures == 0
    assert len(storage.saved) == 1


def test_registry_same_escalated_state_still_persists():
    storage = SpyStorage()
    registry = AgentRegistry(storage=storage)
    agent = _agent(state=AgentState.ESCALATED)
    registry.register(agent)
    storage.saved.clear()

    registry.change_state(
        agent.agent_id,
        AgentState.ESCALATED,
        "re-escalated",
    )

    assert len(storage.saved) == 1
    assert agent.last_state_reason == "re-escalated"


def test_registry_add_evaluation_missing_agent():
    registry = AgentRegistry(storage=SpyStorage())

    with pytest.raises(KeyError, match="Agent not found"):
        registry.add_evaluation("missing", _record())


def test_registry_add_evaluation_failure_and_reset_paths():
    storage = SpyStorage()
    registry = AgentRegistry(storage=storage)
    agent = _agent()
    registry.register(agent)

    registry.add_evaluation(
        agent.agent_id,
        _record(
            reward=-0.8,
            action=GatewayAction.BLOCK,
        ),
    )
    assert agent.consecutive_failures == 1

    registry.add_evaluation(
        agent.agent_id,
        _record(
            reward=-0.7,
            action=GatewayAction.ESCALATE,
        ),
    )
    assert agent.consecutive_failures == 2

    registry.add_evaluation(
        agent.agent_id,
        _record(
            reward=0.9,
            action=GatewayAction.PASS,
        ),
    )

    assert agent.consecutive_failures == 0
    assert agent.performance_window == [-0.8, -0.7, 0.9]
    assert len(agent.evaluation_history) == 3


def test_registry_agents_at_risk_and_count_by_state():
    registry = AgentRegistry(storage=SpyStorage())

    active_bad = _agent("bad")
    active_bad.performance_window = [-0.8, -0.4]

    active_good = _agent("good")
    active_good.performance_window = [0.8, 0.9]

    frozen_bad = _agent(
        "frozen",
        state=AgentState.FROZEN,
    )
    frozen_bad.performance_window = [-1.0]

    registry.register(active_bad)
    registry.register(active_good)
    registry.register(frozen_bad)

    assert [a.agent_id for a in registry.agents_at_risk()] == ["bad"]

    assert registry.count_by_state() == {
        "active": 2,
        "frozen": 1,
    }


class FakeResponse:
    def __init__(
        self,
        *,
        status_code=200,
        data=None,
    ):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data


class FakeAsyncClient:
    response = None
    raised = None
    calls = []

    def __init__(self, *args, **kwargs):
        self.init_args = args
        self.init_kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, **kwargs):
        type(self).calls.append(
            {
                "url": url,
                **kwargs,
            }
        )

        if type(self).raised is not None:
            raise type(self).raised

        return type(self).response


@pytest.fixture
def fake_httpx(monkeypatch):
    FakeAsyncClient.response = None
    FakeAsyncClient.raised = None
    FakeAsyncClient.calls = []

    fake_module = SimpleNamespace(
        AsyncClient=FakeAsyncClient,
    )
    monkeypatch.setitem(
        sys.modules,
        "httpx",
        fake_module,
    )

    return FakeAsyncClient


def _run_report(**kwargs):
    defaults = {
        "fate_vector": {
            "stability": 0.8,
            "distortion": 0.1,
        },
        "existence_rank": "stable",
    }
    defaults.update(kwargs)

    return asyncio.run(
        llm_reporter.generate_llm_report(**defaults)
    )


def test_llm_report_unknown_provider():
    result = _run_report(
        provider="unsupported-provider",
    )

    assert result["report"] == ""
    assert result["provider_used"] == "unsupported-provider"
    assert "Unknown provider" in result["error"]
    assert result["generated_at"]


def test_llm_report_openai_success_with_usage(
    fake_httpx,
):
    fake_httpx.response = FakeResponse(
        data={
            "choices": [
                {
                    "message": {
                        "content": "OpenAI report",
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
        }
    )

    result = _run_report(
        provider="openai",
        model="test-openai",
        api_key="secret",
        robustness=0.9,
        sensitivity=0.2,
        compatibility=0.8,
        lift=0.5,
        possibility=0.7,
        aftermath=0.6,
        style="technical",
    )

    assert result["report"] == "OpenAI report"
    assert result["provider_used"] == "openai"
    assert result["model_used"] == "test-openai"
    assert result["tokens_used"] == {
        "prompt": 11,
        "completion": 7,
        "total": 18,
    }

    call = fake_httpx.calls[-1]
    assert call["url"] == "https://api.openai.com/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer secret"
    assert call["json"]["model"] == "test-openai"


def test_llm_report_opencode_defaults_and_arabic(
    fake_httpx,
    monkeypatch,
):
    monkeypatch.setenv(
        "OPENCODE_API_URL",
        "http://example.test/v1",
    )
    monkeypatch.setenv(
        "OPENCODE_DEFAULT_MODEL",
        "local-model",
    )

    fake_httpx.response = FakeResponse(
        data={
            "choices": [
                {
                    "message": {
                        "content": "Local report",
                    }
                }
            ]
        }
    )

    result = _run_report(
        provider="",
        language="ar",
        style="not-a-real-style",
    )

    assert result["provider_used"] == "opencode"
    assert result["model_used"] == "local-model"
    assert result["tokens_used"] is None

    call = fake_httpx.calls[-1]
    assert call["url"] == "http://example.test/v1/chat/completions"

    prompt = call["json"]["messages"][1]["content"]
    assert "Arabic" in prompt
    assert "N/A" in prompt


def test_llm_report_openai_http_error(
    fake_httpx,
):
    fake_httpx.response = FakeResponse(
        status_code=503,
    )

    result = _run_report(
        provider="openai",
    )

    assert result["report"] == ""
    assert "HTTP 503" in result["error"]


def test_llm_report_anthropic_success(
    fake_httpx,
):
    fake_httpx.response = FakeResponse(
        data={
            "content": [
                {
                    "text": "Anthropic report",
                }
            ],
            "usage": {
                "input_tokens": 12,
                "output_tokens": 5,
            },
        }
    )

    result = _run_report(
        provider="anthropic",
        model="claude-test",
        api_key="anthropic-key",
    )

    assert result["report"] == "Anthropic report"
    assert result["tokens_used"] == {
        "input": 12,
        "output": 5,
    }

    call = fake_httpx.calls[-1]
    assert call["url"] == "https://api.anthropic.com/v1/messages"
    assert call["headers"]["x-api-key"] == "anthropic-key"


def test_llm_report_anthropic_http_error(
    fake_httpx,
):
    fake_httpx.response = FakeResponse(
        status_code=401,
    )

    result = _run_report(
        provider="anthropic",
    )

    assert "HTTP 401" in result["error"]


def test_llm_report_gemini_success(
    fake_httpx,
):
    fake_httpx.response = FakeResponse(
        data={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Gemini"},
                            {"text": "report"},
                        ]
                    }
                }
            ]
        }
    )

    result = _run_report(
        provider="gemini",
        model="gemini-test",
        api_key="gemini-key",
    )

    assert result["report"] == "Gemini report"
    assert result["model_used"] == "gemini-test"


def test_llm_report_gemini_without_candidates(
    fake_httpx,
):
    fake_httpx.response = FakeResponse(
        data={
            "candidates": [],
        }
    )

    result = _run_report(
        provider="gemini",
    )

    assert result["report"] == ""
    assert result["tokens_used"] is None


def test_llm_report_gemini_http_error(
    fake_httpx,
):
    fake_httpx.response = FakeResponse(
        status_code=429,
    )

    result = _run_report(
        provider="gemini",
    )

    assert "HTTP 429" in result["error"]


def test_llm_report_deepseek_success(
    fake_httpx,
):
    fake_httpx.response = FakeResponse(
        data={
            "choices": [
                {
                    "message": {
                        "content": "DeepSeek report",
                    }
                }
            ]
        }
    )

    result = _run_report(
        provider="deepseek",
        model="deepseek-test",
        api_key="deepseek-key",
    )

    assert result["report"] == "DeepSeek report"

    call = fake_httpx.calls[-1]
    assert call["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer deepseek-key"


def test_llm_report_deepseek_http_error(
    fake_httpx,
):
    fake_httpx.response = FakeResponse(
        status_code=500,
    )

    result = _run_report(
        provider="deepseek",
    )

    assert "HTTP 500" in result["error"]


def test_llm_report_exception_is_returned_as_error(
    fake_httpx,
):
    fake_httpx.raised = RuntimeError(
        "network exploded",
    )

    result = _run_report(
        provider="openai",
    )

    assert result["report"] == ""
    assert result["error"] == "network exploded"


def test_error_result_and_utc_timestamp_helpers():
    result = llm_reporter._error_result(
        "boom",
        "provider",
        "model",
        0.0,
    )

    assert result["error"] == "boom"
    assert result["provider_used"] == "provider"
    assert result["model_used"] == "model"
    assert result["generated_at"]

    timestamp = llm_reporter._utc_now_iso()

    assert "+00:00" in timestamp
