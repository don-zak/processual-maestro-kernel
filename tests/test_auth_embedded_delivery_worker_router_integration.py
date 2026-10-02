from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

import processual_api.auth.embedded_delivery_worker as worker_module
from processual_api.auth.delivery_operations_router import router as delivery_operations_router


def test_delivery_operations_router_registers_embedded_worker_lifespan() -> None:
    assert delivery_operations_router.lifespan_context is worker_module.delivery_router_lifespan


def test_included_delivery_router_starts_and_stops_embedded_worker(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_DELIVERY_EMBEDDED_WORKER_ENABLED", "true")
    monkeypatch.setenv("AUTH_DELIVERY_EMBEDDED_WORKER_POLL_INTERVAL_SECONDS", "0.05")

    started = asyncio.Event()
    stopped = asyncio.Event()

    async def fake_loop(*, stop_event, poll_interval_seconds, runtime_factory=worker_module.build_delivery_runtime):
        del poll_interval_seconds, runtime_factory
        started.set()
        await stop_event.wait()
        stopped.set()

    monkeypatch.setattr(worker_module, "run_embedded_delivery_loop", fake_loop)

    app = FastAPI()
    app.include_router(delivery_operations_router)

    with TestClient(app):
        assert started.is_set()
        task = app.state.auth_delivery_embedded_worker_task
        assert task.done() is False

    assert stopped.is_set()
    assert not hasattr(app.state, "auth_delivery_embedded_worker_task")
