from __future__ import annotations

from fastapi import HTTPException, Response
import pytest

from processual_api.cgt_governor.adapters.base import BaseLLMAdapter
from processual_api.cgt_governor.adapters.execution_fanout import (
    ExecutionFanoutSaturatedError,
)
from processual_api.routers import workflows


class FakeAdapter(BaseLLMAdapter):
    def __init__(self, *, configured: bool = True, fail_prompt: str | None = None) -> None:
        self._configured = configured
        self._fail_prompt = fail_prompt
        self.active = 0
        self.max_active = 0

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        del system_prompt, kwargs
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if prompt == self._fail_prompt:
                raise ValueError("sensitive provider failure detail")
            return f"response:{prompt}"
        finally:
            self.active -= 1

    def is_configured(self) -> bool:
        return self._configured

    @property
    def provider_name(self) -> str:
        return "fake"


def request(width: int) -> workflows.LLMOrchestrationRequest:
    return workflows.LLMOrchestrationRequest(
        provider="fake",
        prompts=[f"prompt-{index}" for index in range(width)],
    )


@pytest.mark.asyncio
async def test_narrow_orchestration_uses_shared_governor_only(monkeypatch) -> None:
    adapter = FakeAdapter()
    monkeypatch.setattr(workflows.adapter_registry, "get", lambda provider: adapter)

    result = await workflows.orchestrate_llm(request(8), _user="test-user")

    assert isinstance(result, dict)
    assert result["paced"] is False
    assert result["local_parallelism"] is None
    assert result["plan_reason"] == "shared_governor_only"
    assert [item["response"] for item in result["results"]] == [
        f"response:prompt-{index}" for index in range(8)
    ]


@pytest.mark.asyncio
async def test_broad_single_provider_orchestration_is_paced(monkeypatch) -> None:
    adapter = FakeAdapter()
    monkeypatch.setattr(workflows.adapter_registry, "get", lambda provider: adapter)

    result = await workflows.orchestrate_llm(request(12), _user="test-user")

    assert isinstance(result, dict)
    assert result["paced"] is True
    assert result["local_parallelism"] == 2
    assert result["plan_reason"] == "broad_single_provider"


@pytest.mark.asyncio
async def test_orchestration_returns_structured_adapter_error(monkeypatch) -> None:
    adapter = FakeAdapter(fail_prompt="prompt-1")
    monkeypatch.setattr(workflows.adapter_registry, "get", lambda provider: adapter)

    result = await workflows.orchestrate_llm(request(3), _user="test-user")

    assert isinstance(result, dict)
    assert result["results"][1] == {
        "index": 1,
        "status": "error",
        "error_type": "ValueError",
    }
    assert "sensitive provider failure detail" not in str(result)


@pytest.mark.asyncio
async def test_orchestration_returns_429_on_shared_governor_saturation(
    monkeypatch,
) -> None:
    adapter = FakeAdapter()
    monkeypatch.setattr(workflows.adapter_registry, "get", lambda provider: adapter)

    async def saturated_executor(items, worker, plan):
        del worker, plan
        return [ExecutionFanoutSaturatedError("provider") for _item in items]

    monkeypatch.setattr(workflows, "execute_fanout_plan", saturated_executor)

    result = await workflows.orchestrate_llm(request(2), _user="test-user")

    assert isinstance(result, Response)
    assert result.status_code == 429
    assert result.headers["X-Maestro-Capacity-Reason"] == "execution_fanout"


@pytest.mark.asyncio
async def test_orchestration_rejects_unknown_or_unconfigured_provider(
    monkeypatch,
) -> None:
    monkeypatch.setattr(workflows.adapter_registry, "get", lambda provider: None)
    with pytest.raises(HTTPException) as unknown:
        await workflows.orchestrate_llm(request(1), _user="test-user")
    assert unknown.value.status_code == 404

    adapter = FakeAdapter(configured=False)
    monkeypatch.setattr(workflows.adapter_registry, "get", lambda provider: adapter)
    with pytest.raises(HTTPException) as unconfigured:
        await workflows.orchestrate_llm(request(1), _user="test-user")
    assert unconfigured.value.status_code == 409


@pytest.mark.asyncio
async def test_orchestration_validates_request_bounds(monkeypatch) -> None:
    adapter = FakeAdapter()
    monkeypatch.setattr(workflows.adapter_registry, "get", lambda provider: adapter)

    empty = workflows.LLMOrchestrationRequest(provider="fake", prompts=[])
    with pytest.raises(HTTPException) as empty_error:
        await workflows.orchestrate_llm(empty, _user="test-user")
    assert empty_error.value.status_code == 400

    too_wide = workflows.LLMOrchestrationRequest(
        provider="fake",
        prompts=["prompt"] * 33,
    )
    with pytest.raises(HTTPException) as width_error:
        await workflows.orchestrate_llm(too_wide, _user="test-user")
    assert width_error.value.status_code == 400
