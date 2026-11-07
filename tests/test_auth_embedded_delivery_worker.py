from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import FastAPI

import processual_api.auth.embedded_delivery_worker as worker_module
from processual_api.auth.embedded_delivery_worker import (
    delivery_router_lifespan,
    embedded_delivery_worker_enabled,
    embedded_delivery_worker_poll_interval,
    run_embedded_delivery_loop,
)


class Result:
    claimed = 1
    delivered = 1
    retry_scheduled = 0
    dead_lettered = 0
    stale_finalization = 0


class SequencedDispatcher:
    def __init__(self) -> None:
        self.calls = 0

    async def dispatch_once(self):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("sensitive provider failure text")
        return Result()


class BlockingDispatcher:
    def __init__(self) -> None:
        self.calls = 0

    async def dispatch_once(self):
        self.calls += 1
        return Result()


def test_embedded_worker_is_disabled_by_default() -> None:
    assert embedded_delivery_worker_enabled({}) is False
    assert embedded_delivery_worker_enabled({"AUTH_DELIVERY_EMBEDDED_WORKER_ENABLED": "false"}) is False
    assert embedded_delivery_worker_enabled({"AUTH_DELIVERY_EMBEDDED_WORKER_ENABLED": "true"}) is True
    assert embedded_delivery_worker_enabled({"AUTH_DELIVERY_EMBEDDED_WORKER_ENABLED": "1"}) is True


def test_embedded_worker_poll_interval_is_bounded() -> None:
    assert embedded_delivery_worker_poll_interval({}) == 1.0
    assert embedded_delivery_worker_poll_interval(
        {"AUTH_DELIVERY_EMBEDDED_WORKER_POLL_INTERVAL_SECONDS": "0.25"}
    ) == 0.25

    for value in ("invalid", "0", "0.01", "61"):
        try:
            embedded_delivery_worker_poll_interval(
                {"AUTH_DELIVERY_EMBEDDED_WORKER_POLL_INTERVAL_SECONDS": value}
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe poll interval accepted: {value}")


def test_embedded_loop_survives_batch_failure_without_logging_sensitive_text(caplog) -> None:
    dispatcher = SequencedDispatcher()
    runtime = SimpleNamespace(dispatcher=dispatcher)

    async def scenario() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            run_embedded_delivery_loop(
                stop_event=stop_event,
                poll_interval_seconds=0.05,
                runtime_factory=lambda: runtime,
            )
        )
        for _ in range(50):
            if dispatcher.calls >= 2:
                break
            await asyncio.sleep(0.01)
        stop_event.set()
        await task

    asyncio.run(scenario())

    assert dispatcher.calls >= 2
    assert "identity_delivery_embedded_worker_batch_failed" in caplog.text
    assert "sensitive provider failure text" not in caplog.text


def test_embedded_loop_runtime_unavailable_does_not_raise(caplog) -> None:
    async def scenario() -> None:
        stop_event = asyncio.Event()

        def unavailable_runtime():
            raise RuntimeError("secret-bearing runtime failure")

        await run_embedded_delivery_loop(
            stop_event=stop_event,
            poll_interval_seconds=0.05,
            runtime_factory=unavailable_runtime,
        )

    asyncio.run(scenario())

    assert "identity_delivery_embedded_worker_runtime_unavailable" in caplog.text
    assert "secret-bearing runtime failure" not in caplog.text


def test_lifespan_disabled_does_not_create_worker_task(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_DELIVERY_EMBEDDED_WORKER_ENABLED", "false")
    app = FastAPI()

    async def scenario() -> None:
        async with delivery_router_lifespan(app):
            assert not hasattr(app.state, "auth_delivery_embedded_worker_task")

    asyncio.run(scenario())


def test_lifespan_enabled_starts_and_stops_worker_task(monkeypatch) -> None:
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

    async def scenario() -> None:
        async with delivery_router_lifespan(app):
            await asyncio.wait_for(started.wait(), timeout=1)
            task = app.state.auth_delivery_embedded_worker_task
            assert task.done() is False
        assert stopped.is_set()
        assert not hasattr(app.state, "auth_delivery_embedded_worker_task")

    asyncio.run(scenario())


def test_invalid_embedded_configuration_fails_closed_without_task(monkeypatch, caplog) -> None:
    monkeypatch.setenv("AUTH_DELIVERY_EMBEDDED_WORKER_ENABLED", "true")
    monkeypatch.setenv("AUTH_DELIVERY_EMBEDDED_WORKER_POLL_INTERVAL_SECONDS", "0")
    app = FastAPI()

    async def scenario() -> None:
        async with delivery_router_lifespan(app):
            assert not hasattr(app.state, "auth_delivery_embedded_worker_task")

    asyncio.run(scenario())

    assert "identity_delivery_embedded_worker_configuration_invalid" in caplog.text
