from __future__ import annotations

import asyncio

from fastapi import FastAPI, Query, Response

from processual_api.cgt_governor.adapters.base import BaseLLMAdapter
from processual_api.cgt_governor.adapters.execution_fanout import ExecutionFanoutSaturatedError
from processual_api.cgt_governor.adapters.registry import LLMAdapterRegistry


class SimulatedProviderFailure(RuntimeError):
    pass


class DeterministicLLMAdapter(BaseLLMAdapter):
    def __init__(self, name: str) -> None:
        self._name = name

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        del system_prompt, kwargs
        mode = prompt.rsplit(":", 1)[-1]
        delays = {
            "fast": 0.04,
            "normal": 0.12,
            "slow": 0.35,
            "timeout": 0.60,
            "failure": 0.12,
        }
        await asyncio.sleep(delays[mode])
        if mode == "timeout":
            raise TimeoutError("simulated provider timeout")
        if mode == "failure":
            raise SimulatedProviderFailure("simulated provider failure")
        return mode

    def is_configured(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def default_model(self) -> str:
        return "deterministic-benchmark"


def mode_for_call(request_id: int, slot: int) -> str:
    bucket = (request_id * 7 + slot * 3) % 20
    if bucket < 10:
        return "fast"
    if bucket < 15:
        return "normal"
    if bucket < 18:
        return "slow"
    if bucket == 18:
        return "timeout"
    return "failure"


registry = LLMAdapterRegistry()
for provider_name in ("benchmark-llm-a", "benchmark-llm-b"):
    registry.register(DeterministicLLMAdapter(provider_name))

app = FastAPI()


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/benchmark/execution-mix", response_model=None)
async def execution_mix(
    request_id: int = Query(ge=0),
    width: int = Query(default=8, ge=1, le=32),
    providers: int = Query(default=2, ge=1, le=2),
) -> dict[str, int] | Response:
    async def one(slot: int) -> str:
        provider_index = slot % providers
        adapter = registry.get(f"benchmark-llm-{'a' if provider_index == 0 else 'b'}")
        assert adapter is not None
        mode = mode_for_call(request_id, slot)
        try:
            await adapter.generate(f"benchmark:{request_id}:{slot}:{mode}")
        except TimeoutError:
            return "timeout"
        except SimulatedProviderFailure:
            return "failure"
        return "success"

    outcomes = await asyncio.gather(
        *(one(slot) for slot in range(width)),
        return_exceptions=True,
    )
    saturated = sum(isinstance(outcome, ExecutionFanoutSaturatedError) for outcome in outcomes)
    unexpected = [outcome for outcome in outcomes if isinstance(outcome, Exception) and not isinstance(outcome, ExecutionFanoutSaturatedError)]
    if unexpected:
        raise unexpected[0]
    if saturated:
        return Response(
            status_code=429,
            headers={
                "Retry-After": "1",
                "X-Maestro-Capacity-Reason": "execution_fanout",
            },
        )
    return {
        "success": sum(outcome == "success" for outcome in outcomes),
        "provider_timeouts": sum(outcome == "timeout" for outcome in outcomes),
        "provider_failures": sum(outcome == "failure" for outcome in outcomes),
    }
