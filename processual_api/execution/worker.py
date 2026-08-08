"""Worker runner for durable execution jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from typing import Any

from .durable import DurableJobStore, ExecutionJob, JobLeaseLostError

JobHandler = Callable[[ExecutionJob], Awaitable[Any]]


class DurableWorker:
    """Claim and execute one durable job while renewing its lease.

    Worker cancellation is treated as process/shutdown interruption: the job is
    left running under its lease so another worker can recover it after expiry.
    Business-level cancellation must go through ``request_cancel`` on the store.
    """

    def __init__(
        self,
        *,
        store: DurableJobStore,
        worker_id: str,
        handlers: Mapping[str, JobHandler],
        lease_seconds: float = 30.0,
        heartbeat_interval_seconds: float | None = None,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id cannot be empty")
        if not handlers:
            raise ValueError("at least one domain handler is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")

        interval = heartbeat_interval_seconds
        if interval is None:
            interval = max(min(lease_seconds / 3, lease_seconds - 0.001), 0.001)
        if interval <= 0 or interval >= lease_seconds:
            raise ValueError("heartbeat interval must be positive and smaller than lease_seconds")

        self._store = store
        self._worker_id = worker_id
        self._handlers = dict(handlers)
        self._lease_seconds = lease_seconds
        self._heartbeat_interval_seconds = interval

    async def _heartbeat(self, job: ExecutionJob, lease_token: str) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval_seconds)
            await self._store.heartbeat(
                job_id=job.job_id,
                worker_id=self._worker_id,
                lease_token=lease_token,
                lease_seconds=self._lease_seconds,
            )

    async def run_once(self) -> ExecutionJob | None:
        job = await self._store.claim(
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
            domains=tuple(self._handlers),
        )
        if job is None:
            return None
        if job.lease_token is None:
            raise JobLeaseLostError(f"claimed job has no lease token: {job.job_id}")

        lease_token = job.lease_token
        handler = self._handlers[job.spec.domain]
        handler_task = asyncio.create_task(handler(job))
        heartbeat_task = asyncio.create_task(self._heartbeat(job, lease_token))

        try:
            done, _pending = await asyncio.wait(
                {handler_task, heartbeat_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if heartbeat_task in done:
                heartbeat_error = heartbeat_task.exception()
                if heartbeat_error is not None:
                    handler_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await handler_task
                    raise heartbeat_error

            result = await handler_task
            return await self._store.succeed(
                job_id=job.job_id,
                worker_id=self._worker_id,
                lease_token=lease_token,
                result=result,
            )
        except asyncio.CancelledError:
            handler_task.cancel()
            with suppress(asyncio.CancelledError):
                await handler_task
            raise
        except JobLeaseLostError:
            raise
        except Exception as exc:
            return await self._store.fail(
                job_id=job.job_id,
                worker_id=self._worker_id,
                lease_token=lease_token,
                error=type(exc).__name__,
            )
        finally:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
