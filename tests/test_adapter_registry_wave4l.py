from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from processual_api.cgt_governor.adapters import registry as registry_mod
from processual_api.cgt_governor.adapters.base import BaseLLMAdapter


class FakeAdapter(BaseLLMAdapter):
    def __init__(self, name: str = "Provider One", configured: bool = True) -> None:
        self._name = name
        self._configured = configured
        self.generate_calls: list[dict[str, Any]] = []

    async def generate(self, prompt: str, system_prompt: str | None = None, **kwargs: Any) -> str:
        self.generate_calls.append({"prompt": prompt, "system_prompt": system_prompt, **kwargs})
        return "generated"

    def is_configured(self) -> bool:
        return self._configured

    async def is_available(self) -> bool:
        return self._configured

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def default_model(self) -> str:
        return "model-1"


def test_register_get_all_and_configured_normalize_provider_names() -> None:
    registry = registry_mod.LLMAdapterRegistry()
    configured = FakeAdapter("Provider One", configured=True)
    disabled = FakeAdapter("Provider Two", configured=False)

    registry.register(configured)
    registry.register(disabled)

    wrapped = registry.get("PROVIDER ONE")
    assert isinstance(wrapped, registry_mod._GovernedLLMAdapter)
    assert wrapped is registry.get("provider_one")
    assert wrapped.provider_name == "Provider One"
    assert wrapped.default_model == "model-1"
    assert wrapped._adapter is configured
    assert registry.get("missing") is None

    snapshot = registry.all()
    assert set(snapshot) == {"provider_one", "provider_two"}
    snapshot.clear()
    assert set(registry.all()) == {"provider_one", "provider_two"}
    assert set(registry.configured()) == {"provider_one"}


@pytest.mark.asyncio
async def test_governed_adapter_delegates_health_and_runs_generation_through_fanout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = FakeAdapter()
    governed = registry_mod._GovernedLLMAdapter(adapter)
    fanout = AsyncMock()

    async def run_operation(provider_name: str, operation):
        fanout(provider_name)
        return await operation()

    monkeypatch.setattr(registry_mod, "run_with_execution_fanout", run_operation)

    assert governed.is_configured() is True
    assert await governed.is_available() is True
    assert await governed.generate("hello", system_prompt="system", temperature=0.2) == "generated"
    fanout.assert_awaited_once_with("Provider One")
    assert adapter.generate_calls == [
        {"prompt": "hello", "system_prompt": "system", "temperature": 0.2}
    ]


def test_default_prefers_requested_provider_then_falls_back_to_first_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = registry_mod.LLMAdapterRegistry()
    first = FakeAdapter("First", configured=True)
    second = FakeAdapter("Second", configured=True)
    registry.register(first)
    registry.register(second)

    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "second")
    assert registry.default() is registry.get("second")

    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "missing")
    assert registry.default() is registry.get("first")

    monkeypatch.delenv("LLM_DEFAULT_PROVIDER", raising=False)
    assert registry.default() is registry.get("first")

    empty = registry_mod.LLMAdapterRegistry()
    empty.register(FakeAdapter("Disabled", configured=False))
    assert empty.default() is None


def test_list_providers_returns_public_summary() -> None:
    registry = registry_mod.LLMAdapterRegistry()
    registry.register(FakeAdapter("Provider One", configured=True))
    registry.register(FakeAdapter("Provider Two", configured=False))

    assert registry.list_providers() == [
        {"name": "Provider One", "configured": True, "default_model": "model-1"},
        {"name": "Provider Two", "configured": False, "default_model": "model-1"},
    ]


def test_registering_governed_adapter_does_not_double_wrap() -> None:
    registry = registry_mod.LLMAdapterRegistry()
    governed = registry_mod._GovernedLLMAdapter(FakeAdapter("Already Governed"))

    registry.register(governed)

    assert registry.get("already_governed") is governed


def test_governed_adapter_forwards_unknown_attributes() -> None:
    adapter = FakeAdapter()
    adapter.extra_value = "extra"  # type: ignore[attr-defined]
    governed = registry_mod._GovernedLLMAdapter(adapter)

    assert governed.extra_value == "extra"
