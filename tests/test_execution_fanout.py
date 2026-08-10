from __future__ import annotations

import asyncio

import pytest

import processual_api.cgt_governor.adapters.execution_fanout as fanout_module
from processual_api.cgt_governor.adapters.base import BaseLLMAdapter
from processual_api.cgt_governor.adapters.execution_fanout import (
    ExecutionFanoutReservation,
    InMemoryExecutionFanoutBackend,
)
from processual_api.cgt_governor.adapters.registry import LLMAdapterRegistry


@pytest.mark.asyncio
async def test_execution_fanout_global_limit_is_atomic() -> None:
    backend = InMemoryExecutionFanoutBackend()

    async def reserve(index: int):
        return await backend.reserve(
            reservation=ExecutionFanoutReservation(f"lease-{index}", f"provider-{index}"),
            global_limit=3,
            provider_limit=3,
            lease_seconds=60,
        )

    decisions = await asyncio.gather(*(reserve(index) for index in range(10)))

    admitted = [decision for decision in decisions if decision.admitted]
    rejected = [decision for decision in decisions if not decision.admitted]
    assert len(admitted) == 3
    assert rejected
    assert all(decision.reason == "global" for decision in rejected)


@pytest.mark.asyncio
async def test_execution_fanout_provider_limit_is_shared() -> None:
    backend = InMemoryExecutionFanoutBackend()

    first = await backend.reserve(
        reservation=ExecutionFanoutReservation("one", "provider-a"),
        global_limit=10,
        provider_limit=2,
        lease_seconds=60,
    )
    second = await backend.reserve(
        reservation=ExecutionFanoutReservation("two", "provider-a"),
        global_limit=10,
        provider_limit=2,
        lease_seconds=60,
    )
    third = await backend.reserve(
        reservation=ExecutionFanoutReservation("three", "provider-a"),
        global_limit=10,
        provider_limit=2,
        lease_seconds=60,
    )
    other = await backend.reserve(
        reservation=ExecutionFanoutReservation("four", "provider-b"),
        global_limit=10,
        provider_limit=2,
        lease_seconds=60,
    )

    assert first.admitted is True
    assert second.admitted is True
    assert third.admitted is False
    assert third.reason == "provider"
    assert other.admitted is True


@pytest.mark.asyncio
async def test_execution_fanout_renewal_does_not_recreate_expired_lease(monkeypatch) -> None:
    backend = InMemoryExecutionFanoutBackend()
    reservation = ExecutionFanoutReservation("one", "provider-a")
    now = 100.0
    monkeypatch.setattr(fanout_module.time, "monotonic", lambda: now)

    admitted = await backend.reserve(
        reservation=reservation,
        global_limit=4,
        provider_limit=4,
        lease_seconds=5,
    )
    assert admitted.admitted is True

    now = 103.0
    assert await backend.renew(reservation, lease_seconds=5) is True

    now = 108.0
    assert await backend.renew(reservation, lease_seconds=5) is False


class _FakeAdapter(BaseLLMAdapter):
    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        self.calls += 1
        return f"{system_prompt or ''}:{prompt}"

    def is_configured(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "Fake Provider"

    @property
    def default_model(self) -> str:
        return "fake-model"


@pytest.mark.asyncio
async def test_registry_wrapper_preserves_adapter_contract(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTION_FANOUT_ENABLED", "false")
    registry = LLMAdapterRegistry()
    adapter = _FakeAdapter()
    registry.register(adapter)

    governed = registry.get("fake_provider")
    assert governed is not None
    assert governed.provider_name == "Fake Provider"
    assert governed.default_model == "fake-model"
    assert governed.is_configured() is True
    assert await governed.generate("hello", system_prompt="system") == "system:hello"
    assert adapter.calls == 1
