"""Worker runner for durable execution jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from typing import Any

from .capacity import (
    DomainCapacityController,
    DomainCapacityLeaseLostError,
    DomainCapacityReservation,
    DomainCapacitySaturatedError,
)
from .durable import DurableJobStore, ExecutionJob, JobLeaseLostError

JobHandler = Callable[[ExecutionJob], Awaitable[Any]]


class DurableWorker:
    """Claim and execute one durable job while renewing its leases.

    Worker cancellation is treated as process/shutdown interruption: the job is
    left running under its durable lease so another worker can recover it after
    expiry. Business-level cancellation must go through ``request_cancel`` on
    the store.

    When a domain-capacity controller is configured, a durable claim does not
    start its handler until domain capacity is admitted. Saturated claims are
    requeued without consuming an execution attempt.

    Domain-filtered claims remain the default. A dedicated queue whose workers
    can safely handle every job may opt into unfiltered claims so stores with an
    atomic unfiltered claim path can avoid optimistic-transaction contention.
    """

    def __init__(
        self,
        *,
        store: DurableJobStore,
        worker_id: str,
        handlers: Mapping[str, JobHandler],
        lease_seconds: float = 30.0,
        heartbeat_interval_seconds: float | None = None,
        capacity: DomainCapacityController | None = None,
        capacity_heartbeat_interval_seconds: float = 5.0,
        capacity_requeue_delay_seconds: float = 0.05,
        unfiltered_claims: bool = False,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id cannot be empty")
        if not handlers:
            raise ValueError("at least one domain handler is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if capacity_heartbeat_interval_seconds <= 0:
            raise ValueError("capacity heartbeat interval must be positive")
        if capacity_requeue_delay_seconds < 0:
            raise ValueError("capacity requeue delay cannot be negative")

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
        self._capacity = capacity
        self._capacity_heartbeat_interval_seconds = capacity_heartbeat_interval_seconds
        self._capacity_requeue_delay_seconds = capacity_requeue_delay_seconds
        self._unfiltered_claims = unfiltered_claims

    async def _heartbeat(self, job: ExecutionJob, lease_token: str) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval_seconds)
            await self._store.heartbeat(
                job_id=job.job_id,
                worker_id=self._worker_id,
                lease_token=lease_token,
                lease_seconds=self._lease_seconds,
            )

    async def _capacity_heartbeat(self, reservation: DomainCapacityReservation) -> None:
        if self._capacity is None:
            return
        while True:
            await asyncio.sleep(self._capacity_heartbeat_interval_seconds)
            await self._capacity.renew(reservation)

    async def _release_unstarted(self, job: ExecutionJob, lease_token: str) -> ExecutionJob:
        return await self._store.release_unstarted_claim(
            job_id=job.job_id,
            worker_id=self._worker_id,
            lease_token=lease_token,
            delay_seconds=self._capacity_requeue_delay_seconds,
        )

    async def run_once(self) -> ExecutionJob | None:
        claim_domains = None if self._unfiltered_claims else tuple(self._handlers)
        job = await self._store.claim(
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
            domains=claim_domains,
        )
        if job is None:
            return None
        if job.spec.domain not in self._handlers:
            raise RuntimeError(
                f"unfiltered durable worker claimed unsupported domain: {job.spec.domain}"
            )
        if job.lease_token is None:
            raise JobLeaseLostError(f"claimed job has no lease token: {job.job_id}")

        lease_token = job.lease_token
        reservation: DomainCapacityReservation | None = None
        if self._capacity is not None:
            try:
                reservation = await self._capacity.acquire(
                    domain=job.spec.domain,
                    priority=job.spec.priority,
                )
            except DomainCapacitySaturatedError:
                return await self._release_unstarted(job, lease_token)

        handler = self._handlers[job.spec.domain]
        handler_task = asyncio.create_task(handler(job))
        heartbeat_task = asyncio.create_task(self._heartbeat(job, lease_token))
        capacity_task = (
            asyncio.create_task(self._capacity_heartbeat(reservation))
            if reservation is not None
            else None
        )

        try:
            watched = {handler_task, heartbeat_task}
            if capacity_task is not None:
                watched.add(capacity_task)
            done, _pending = await asyncio.wait(
                watched,
                return_when=asyncio.FIRST_COMPLETED,
            )

            for lease_task in (heartbeat_task, capacity_task):
                if lease_task is not None and lease_task in done:
                    lease_error = lease_task.exception()
                    if lease_error is not None:
                        handler_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await handler_task
                        raise lease_error

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
        except (JobLeaseLostError, DomainCapacityLeaseLostError):
            raise
        except Exception as exc:
            return await self._store.fail(
                job_id=job.job_id,
                worker_id=self._worker_id,
                lease_token=lease_token,
                error=type(exc).__name__,
            )
        finally:
            for task in (heartbeat_task, capacity_task):
                if task is not None:
                    task.cancel()
            for task in (heartbeat_task, capacity_task):
                if task is not None:
                    with suppress(asyncio.CancelledError):
                        await task
            if reservation is not None and self._capacity is not None:
                with suppress(Exception):
                    await self._capacity.release(reservation)
