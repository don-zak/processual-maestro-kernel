import asyncio
import os
import uuid

import pytest
import pytest_asyncio
import redis.asyncio as redis

from processual_api.execution.adaptive import (
    AdaptiveConcurrencyController,
    AdaptiveConcurrencyGate,
    AdaptiveConcurrencyPolicy,
    AdaptiveTelemetrySampler,
)
from processual_api.execution.durable import InMemoryDurableJobStore, JobSpec, JobStatus
from processual_api.execution.pool import DurableWorkerPool, DurableWorkerPoolPolicy
from processual_api.execution.redis_store import RedisDurableJobStore
from processual_api.execution.worker import DurableWorker


@pytest_asyncio.fixture
async def redis_client():
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    await client.ping()
    yield client
    await client.aclose()


async def wait_for_redis_time(redis_client, target: float) -> None:
    async with asyncio.timeout(0.5):
        while True:
            seconds, micros = await redis_client.time()
            now = float(seconds) + float(micros) / 1_000_000
            if now >= target:
                return
            await asyncio.sleep(0)


async def wait_for_status(store, job_id: str, status: JobStatus) -> None:
    async with asyncio.timeout(0.5):
        while True:
            job = await store.get(job_id)
            if job.status is status:
                return
            await asyncio.sleep(0)


def fixed_gate(limit: int = 4) -> AdaptiveConcurrencyGate:
    return AdaptiveConcurrencyGate(
        AdaptiveConcurrencyController(
            AdaptiveConcurrencyPolicy(
                minimum=1,
                maximum=limit,
                latency_target_ms=100.0,
                recovery_windows=3,
                pressure_windows=2,
                ewma_alpha=1.0,
            ),
            initial_limit=limit,
        )
    )


@pytest.mark.asyncio
async def test_cancelled_worker_is_recovered_by_replacement_node(redis_client) -> None:
    prefix = f"{{qualification-node-loss-{uuid.uuid4().hex}}}:durable"
    first_store = RedisDurableJobStore(redis_client, prefix=prefix)
    second_store = RedisDurableJobStore(redis_client, prefix=prefix)
    submitted = await first_store.submit(
        JobSpec(idempotency_key="node-loss", domain="provider", payload={})
    )
    started = asyncio.Event()

    async def interrupted_handler(job):
        started.set()
        await asyncio.Event().wait()
        return job.job_id

    first_worker = DurableWorker(
        store=first_store,
        worker_id="node-a",
        handlers={"provider": interrupted_handler},
        lease_seconds=0.08,
        heartbeat_interval_seconds=0.02,
    )

    first_run = asyncio.create_task(first_worker.run_once())
    await asyncio.wait_for(started.wait(), timeout=0.2)
    first_run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first_run

    abandoned = await first_store.get(submitted.job.job_id)
    assert abandoned.status is JobStatus.RUNNING
    assert abandoned.worker_id == "node-a"
    assert abandoned.lease_expires_at is not None

    await wait_for_redis_time(redis_client, abandoned.lease_expires_at)
    assert await second_store.recover_expired_leases() == 1

    async def replacement_handler(job):
        return {"resumed_by": "node-b", "job_id": job.job_id}

    replacement = DurableWorker(
        store=second_store,
        worker_id="node-b",
        handlers={"provider": replacement_handler},
        lease_seconds=0.5,
    )
    completed = await replacement.run_once()

    assert completed is not None
    assert completed.job_id == submitted.job.job_id
    assert completed.status is JobStatus.SUCCEEDED
    assert completed.attempt == 2
    assert completed.result["resumed_by"] == "node-b"


@pytest.mark.asyncio
async def test_infrastructure_failure_does_not_feed_provider_pressure() -> None:
    class FailingClaimStore(InMemoryDurableJobStore):
        def __init__(self) -> None:
            super().__init__()
            self.fail_next_claim = True

        async def claim(self, **kwargs):
            if self.fail_next_claim:
                self.fail_next_claim = False
                raise ConnectionError("redis unavailable")
            return await super().claim(**kwargs)

    store = FailingClaimStore()
    await store.submit(JobSpec(idempotency_key="healthy", domain="provider", payload={}))
    gate = fixed_gate(4)
    sampler = AdaptiveTelemetrySampler(window_size=1)
    errors: list[BaseException] = []

    async def handler(job):
        return job.job_id

    worker = DurableWorker(
        store=store,
        worker_id="infra-aware",
        handlers={"provider": handler},
    )
    pool = DurableWorkerPool(
        store=store,
        workers=[worker],
        adaptive_gate=gate,
        adaptive_sampler=sampler,
        on_worker_error=errors.append,
        policy=DurableWorkerPoolPolicy(
            idle_poll_seconds=0.005,
            recovery_interval_seconds=0.02,
        ),
    )

    await pool.start()
    try:
        async with asyncio.timeout(0.5):
            while not errors:
                await asyncio.sleep(0)
        assert isinstance(errors[0], ConnectionError)
        assert gate.current_limit == 4
        assert sampler.pending == 0

        job_id = next(iter(store._jobs))  # type: ignore[attr-defined]
        await wait_for_status(store, job_id, JobStatus.SUCCEEDED)
        assert gate.current_limit == 4
    finally:
        await pool.stop(graceful_timeout_seconds=0.5)


@pytest.mark.asyncio
async def test_duplicate_submissions_execute_once_across_worker_pool(redis_client) -> None:
    prefix = f"{{qualification-idempotency-{uuid.uuid4().hex}}}:durable"
    store = RedisDurableJobStore(redis_client, prefix=prefix)
    request = JobSpec(
        idempotency_key="duplicate-across-nodes",
        domain="provider",
        payload={"operation": "charge-once"},
    )

    submissions = await asyncio.gather(*(store.submit(request) for _ in range(24)))
    assert len({item.job.job_id for item in submissions}) == 1
    assert sum(item.created for item in submissions) == 1
    job_id = submissions[0].job.job_id

    executions = 0

    async def handler(job):
        nonlocal executions
        executions += 1
        return {"executed": job.job_id}

    workers = [
        DurableWorker(
            store=RedisDurableJobStore(redis_client, prefix=prefix),
            worker_id=f"node-{index}",
            handlers={"provider": handler},
        )
        for index in range(4)
    ]
    pool = DurableWorkerPool(
        store=store,
        workers=workers,
        policy=DurableWorkerPoolPolicy(
            idle_poll_seconds=0.002,
            recovery_interval_seconds=0.05,
        ),
    )

    await pool.start()
    try:
        await wait_for_status(store, job_id, JobStatus.SUCCEEDED)
    finally:
        await pool.stop(graceful_timeout_seconds=0.5)

    completed = await store.get(job_id)
    assert completed.status is JobStatus.SUCCEEDED
    assert completed.attempt == 1
    assert executions == 1
