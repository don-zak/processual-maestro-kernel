"""Continuous durable worker-pool orchestration.

The pool is opt-in and never starts from application import or FastAPI startup.
Callers explicitly construct it around durable stores and workers.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass

from .durable import DurableJobStore
from .worker import DurableWorker


@dataclass(frozen=True, slots=True)
class DurableWorkerPoolPolicy:
    idle_poll_seconds: float = 0.05
    recovery_interval_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.idle_poll_seconds <= 0:
            raise ValueError("idle_poll_seconds must be positive")
        if self.recovery_interval_seconds <= 0:
            raise ValueError("recovery_interval_seconds must be positive")


class DurableWorkerPool:
    """Run durable workers continuously with periodic expired-lease recovery."""

    def __init__(
        self,
        *,
        store: DurableJobStore,
        workers: Sequence[DurableWorker],
        policy: DurableWorkerPoolPolicy | None = None,
        on_worker_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        if not workers:
            raise ValueError("at least one durable worker is required")
        self._store = store
        self._workers = tuple(workers)
        self._policy = policy or DurableWorkerPoolPolicy()
        self._on_worker_error = on_worker_error
        self._stop = asyncio.Event()
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def running(self) -> bool:
        return bool(self._tasks) and not self._stop.is_set()

    async def _worker_loop(self, worker: DurableWorker) -> None:
        while not self._stop.is_set():
            try:
                completed = await worker.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._on_worker_error is not None:
                    self._on_worker_error(exc)
                await asyncio.sleep(self._policy.idle_poll_seconds)
                continue
            if completed is None:
                await asyncio.sleep(self._policy.idle_poll_seconds)

    async def _recovery_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self._store.recover_expired_leases()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._on_worker_error is not None:
                    self._on_worker_error(exc)
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self._policy.recovery_interval_seconds,
                )
            except TimeoutError:
                pass

    async def start(self) -> None:
        if self._tasks:
            raise RuntimeError("durable worker pool is already started")
        self._stop.clear()
        tasks = {
            asyncio.create_task(self._worker_loop(worker))
            for worker in self._workers
        }
        tasks.add(asyncio.create_task(self._recovery_loop()))
        self._tasks = tasks

    async def stop(self, *, graceful_timeout_seconds: float = 5.0) -> None:
        if graceful_timeout_seconds < 0:
            raise ValueError("graceful_timeout_seconds cannot be negative")
        if not self._tasks:
            self._stop.set()
            return

        self._stop.set()
        done, pending = await asyncio.wait(
            self._tasks,
            timeout=graceful_timeout_seconds,
        )
        for task in pending:
            task.cancel()
        for task in pending:
            with suppress(asyncio.CancelledError):
                await task
        for task in done:
            if task.cancelled():
                continue
            with suppress(Exception):
                task.result()
        self._tasks.clear()

    async def run_until_stopped(self) -> None:
        await self.start()
        await self._stop.wait()

    def request_stop(self) -> None:
        self._stop.set()
