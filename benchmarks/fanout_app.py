from __future__ import annotations

import asyncio

from fastapi import FastAPI, Query

from processual_api.middleware.runtime_capacity import RuntimeCapacityMiddleware

app = FastAPI()
app.add_middleware(RuntimeCapacityMiddleware)


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/benchmark/fanout")
async def fanout(
    width: int = Query(default=4, ge=1, le=32),
    delay_ms: int = Query(default=25, ge=1, le=250),
) -> dict[str, int]:
    """Deterministic I/O fan-out harness; never calls an external provider."""

    async def one() -> None:
        await asyncio.sleep(delay_ms / 1000)

    await asyncio.gather(*(one() for _ in range(width)))
    return {"fanout": width, "delay_ms": delay_ms}
