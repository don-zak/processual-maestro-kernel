import asyncio
import os

import pytest

from benchmarks.durable_worker_scale import percentile, run_scale_scenario
from processual_api.execution.capacity import (
    DomainCapacityController,
    DomainCapacityPolicy,
    InMemoryDomainCapacityBackend,
)
from processual_api.execution.durable import ExecutionPriority, InMemoryDurableJobStore, JobSpec, JobStatus
from processual_api.execution.pool import DurableWorkerPool, DurableWorkerPoolPolicy
from processual_api.execution.worker import DurableWorker


@pytest.mark.parametrize(
    ("values", "q", "expected"),
    [
        ([1.0], 0.95, 1.0),
        ([1.0, 2.0, 3.0, 4.0], 0.50, 2.0),
        ([1.0, 2.0, 3.0, 4.0], 0.95, 4.0),
        ([], 0.99, 0.0),
    ],
)
def test_percentile_is_deterministic(values, q, expected) -> None:
    assert percentile(values, q) == expected


@pytest.mark.asyncio
async def test_scale_harness_completes_without_true_errors_and_improves_with_workers() -> None:
    redis_url = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
    results = [
        await run_scale_scenario(
            redis_url=redis_url,
            workers=workers,
            jobs=24,
            handler_delay_seconds=0.02,
        )
        for workers in (1, 2, 4)
    ]

    assert all(result.completed == 24 for result in results)
    assert all(result.true_errors == 0 for result in results)
    assert results[1].successful_workflows_per_second > results[0].successful_workflows_per_second
    assert results[2].successful_workflows_per_second > results[1].successful_workflows_per_second
    assert results[2].queue_delay_p95_ms < results[0].queue_delay_p95_ms


@pytest.mark.asyncio
async def test_noisy_neighbor_domain_does_not_starve_critical_domain() -> None:
    store = InMemoryDurableJobStore()
    capacity = DomainCapacityController(
        backend=InMemoryDomainCapacityBackend(),
        policy=DomainCapacityPolicy(
            global_limit=3,
            domain_limits={"batch": 2, "noc": 2},
            emergency_reserve=1,
        ),
        lease_seconds=0.2,
        wait_seconds=0,
        retry_seconds=0.005,
    )
    batch_release = asyncio.Event()
    noc_done = asyncio.Event()

    async def batch_handler(job):
        await batch_release.wait()
        return job.job_id

    async def noc_handler(job):
        noc_done.set()
        return job.job_id

    workers = [
        DurableWorker(
            store=store,
            worker_id=f"batch-{index}",
            handlers={"batch": batch_handler},
            capacity=capacity,
            lease_seconds=0.2,
            heartbeat_interval_seconds=0.05,
            capacity_heartbeat_interval_seconds=0.05,
            capacity_requeue_delay_seconds=0.005,
        )
        for index in range(3)
    ]
    workers.append(
        DurableWorker(
            store=store,
            worker_id="noc-critical",
            handlers={"noc": noc_handler},
            capacity=capacity,
            lease_seconds=0.2,
            heartbeat_interval_seconds=0.05,
            capacity_heartbeat_interval_seconds=0.05,
            capacity_requeue_delay_seconds=0.005,
        )
    )
    pool = DurableWorkerPool(
        store=store,
        workers=workers,
        policy=DurableWorkerPoolPolicy(idle_poll_seconds=0.002, recovery_interval_seconds=0.02),
    )

    for index in range(8):
        await store.submit(
            JobSpec(
                idempotency_key=f"batch-{index}",
                domain="batch",
                payload={},
                priority=ExecutionPriority.BATCH,
            )
        )
    critical = await store.submit(
        JobSpec(
            idempotency_key="noc-critical",
            domain="noc",
            payload={},
            priority=ExecutionPriority.EMERGENCY,
        )
    )

    await pool.start()
    try:
        await asyncio.wait_for(noc_done.wait(), timeout=0.5)
        deadline = asyncio.get_running_loop().time() + 0.5
        while True:
            status = await store.get(critical.job.job_id)
            if status.status is JobStatus.SUCCEEDED:
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("critical NOC job was starved by batch load")
            await asyncio.sleep(0.005)

        assert status.attempt == 1
        batch_running = 0
        for index in range(8):
            job = await store.get((await store.submit(JobSpec(
                idempotency_key=f"batch-{index}",
                domain="batch",
                payload={},
                priority=ExecutionPriority.BATCH,
            ))).job.job_id)
            if job.status is JobStatus.RUNNING:
                batch_running += 1
        assert batch_running <= 2
    finally:
        batch_release.set()
        await pool.stop(graceful_timeout_seconds=0.5)
