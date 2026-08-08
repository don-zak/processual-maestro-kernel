import asyncio
import os
import uuid

import pytest
import pytest_asyncio
import redis.asyncio as redis

from processual_api.execution.capacity import (
    DomainCapacityController,
    DomainCapacityPolicy,
    RedisDomainCapacityBackend,
)
from processual_api.execution.durable import ExecutionPriority, JobSpec, JobStatus
from processual_api.execution.pool import DurableWorkerPool, DurableWorkerPoolPolicy
from processual_api.execution.redis_store_optimized import OptimizedRedisDurableJobStore
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


async def wait_for_succeeded(store, job_ids: list[str], *, timeout_seconds: float) -> None:
    async with asyncio.timeout(timeout_seconds):
        while True:
            jobs = [await store.get(job_id) for job_id in job_ids]
            if all(job.status is JobStatus.SUCCEEDED for job in jobs):
                return
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_eight_redis_workers_preserve_emergency_capacity_under_batch_pressure(
    redis_client,
) -> None:
    token = uuid.uuid4().hex
    store = OptimizedRedisDurableJobStore(
        redis_client,
        prefix=f"{{qualify-eight-{token}}}:durable",
    )
    capacity = DomainCapacityController(
        backend=RedisDomainCapacityBackend(
            redis_client,
            prefix=f"{{qualify-capacity-{token}}}",
        ),
        policy=DomainCapacityPolicy(
            global_limit=8,
            domain_limits={"batch": 7, "noc": 2},
            emergency_reserve=1,
        ),
        lease_seconds=1.0,
        wait_seconds=0,
        retry_seconds=0.005,
    )

    batch_release = asyncio.Event()
    seven_batch_started = asyncio.Event()
    noc_completed = asyncio.Event()
    batch_started = 0
    noc_finished = 0

    async def batch_handler(job):
        nonlocal batch_started
        batch_started += 1
        if batch_started >= 7:
            seven_batch_started.set()
        await batch_release.wait()
        return job.job_id

    async def noc_handler(job):
        nonlocal noc_finished
        noc_finished += 1
        if noc_finished >= 2:
            noc_completed.set()
        return job.job_id

    workers = [
        DurableWorker(
            store=store,
            worker_id=f"qualify-eight-{index}",
            handlers={"batch": batch_handler, "noc": noc_handler},
            capacity=capacity,
            lease_seconds=1.0,
            heartbeat_interval_seconds=0.1,
            capacity_heartbeat_interval_seconds=0.1,
            capacity_requeue_delay_seconds=0.002,
            unfiltered_claims=True,
        )
        for index in range(8)
    ]
    pool = DurableWorkerPool(
        store=store,
        workers=workers,
        policy=DurableWorkerPoolPolicy(
            idle_poll_seconds=0.002,
            recovery_interval_seconds=0.05,
        ),
    )

    batch_jobs = []
    for index in range(24):
        submitted = await store.submit(
            JobSpec(
                idempotency_key=f"qualify-batch-{token}-{index}",
                domain="batch",
                payload={},
                priority=ExecutionPriority.BATCH,
            )
        )
        batch_jobs.append(submitted.job.job_id)

    await pool.start()
    try:
        await asyncio.wait_for(seven_batch_started.wait(), timeout=2.0)

        noc_jobs = []
        for index in range(2):
            submitted = await store.submit(
                JobSpec(
                    idempotency_key=f"qualify-noc-{token}-{index}",
                    domain="noc",
                    payload={},
                    priority=ExecutionPriority.EMERGENCY,
                )
            )
            noc_jobs.append(submitted.job.job_id)

        await asyncio.wait_for(noc_completed.wait(), timeout=1.0)
        await wait_for_succeeded(store, noc_jobs, timeout_seconds=1.0)

        for job_id in noc_jobs:
            job = await store.get(job_id)
            assert job.status is JobStatus.SUCCEEDED
            assert job.attempt == 1

        running_batch = 0
        for job_id in batch_jobs:
            job = await store.get(job_id)
            if job.status is JobStatus.RUNNING:
                running_batch += 1
        assert running_batch <= 7
    finally:
        batch_release.set()
        await pool.stop(graceful_timeout_seconds=2.0)
