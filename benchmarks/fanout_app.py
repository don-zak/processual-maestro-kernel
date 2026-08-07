from __future__ import annotations

import asyncio

from fastapi import FastAPI, Query, Response

from processual_api.cgt_governor.adapters.execution_fanout import (
    ExecutionFanoutSaturatedError,
    run_with_execution_fanout,
)
from processual_api.middleware.runtime_capacity import RuntimeCapacityMiddleware

app = FastAPI()
app.add_middleware(RuntimeCapacityMiddleware)


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/benchmark/fanout", response_model=None)
async def fanout(
    width: int = Query(default=4, ge=1, le=32),
    delay_ms: int = Query(default=25, ge=1, le=250),
) -> dict[str, int] | Response:
    """Deterministic provider fan-out harness with no external network calls."""

    async def simulated_provider_call() -> None:
        await asyncio.sleep(delay_ms / 1000)

    async def one() -> None:
        await run_with_execution_fanout(
            "benchmark-provider",
            simulated_provider_call,
        )

    outcomes = await asyncio.gather(
        *(one() for _ in range(width)),
        return_exceptions=True,
    )
    saturated = sum(isinstance(outcome, ExecutionFanoutSaturatedError) for outcome in outcomes)
    other_errors = [
        outcome
        for outcome in outcomes
        if isinstance(outcome, Exception) and not isinstance(outcome, ExecutionFanoutSaturatedError)
    ]
    if other_errors:
        raise other_errors[0]
    if saturated:
        return Response(
            status_code=429,
            headers={
                "Retry-After": "1",
                "X-Maestro-Capacity-Reason": "execution_fanout",
            },
        )
    return {"fanout": width, "delay_ms": delay_ms}
