"""Operational service facade for durable execution.

The service is intentionally explicit: constructing it has no side effects and
starting workers requires an explicit ``start`` call. This keeps durable worker
availability separate from FastAPI process startup and admission paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .durable import DurableJobStore, ExecutionJob, JobSpec, SubmitResult
from .pool import DurableWorkerPool


@dataclass(frozen=True, slots=True)
class DurableExecutionHealth:
    running: bool
    state: str


class DurableExecutionService:
    """Submit, inspect, cancel, and supervise durable workflow execution."""

    def __init__(
        self,
        *,
        store: DurableJobStore,
        pool: DurableWorkerPool | None = None,
    ) -> None:
        self._store = store
        self._pool = pool

    async def submit(self, spec: JobSpec) -> SubmitResult:
        return await self._store.submit(spec)

    async def status(self, job_id: str) -> ExecutionJob:
        return await self._store.get(job_id)

    async def cancel(self, job_id: str) -> ExecutionJob:
        return await self._store.request_cancel(job_id)

    async def start(self) -> None:
        if self._pool is None:
            raise RuntimeError("durable execution worker pool is not configured")
        await self._pool.start()

    async def stop(self, *, graceful_timeout_seconds: float = 5.0) -> None:
        if self._pool is None:
            return
        await self._pool.stop(graceful_timeout_seconds=graceful_timeout_seconds)

    def health(self) -> DurableExecutionHealth:
        if self._pool is None:
            return DurableExecutionHealth(running=False, state="not_configured")
        if self._pool.running:
            return DurableExecutionHealth(running=True, state="running")
        return DurableExecutionHealth(running=False, state="stopped")

    async def result(self, job_id: str) -> Any:
        """Return the current persisted result without waiting for completion."""

        job = await self.status(job_id)
        return job.result
