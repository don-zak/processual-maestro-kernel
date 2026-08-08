from __future__ import annotations

import asyncio

from fastapi import FastAPI, Response
from prometheus_client import generate_latest

from processual_api.cgt_governor.adapters.base import BaseLLMAdapter
from processual_api.cgt_governor.adapters.registry import adapter_registry
from processual_api.routers import workflows


class DeterministicOrchestrationAdapter(BaseLLMAdapter):
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        del system_prompt, kwargs
        await asyncio.sleep(0.04)
        return f"ok:{prompt}"

    def is_configured(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "benchmark-orchestration"

    @property
    def default_model(self) -> str:
        return "deterministic-orchestration"


adapter_registry.register(DeterministicOrchestrationAdapter())

app = FastAPI()
app.include_router(workflows.router)
app.dependency_overrides[workflows.get_current_user] = lambda: "benchmark-user"


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type="text/plain")
