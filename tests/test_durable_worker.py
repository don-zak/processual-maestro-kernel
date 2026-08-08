import asyncio

import pytest

from processual_api.execution.durable import (
    InMemoryDurableJobStore,
    JobSpec,
    JobStatus,
    RetryPolicy,
)
from processual_api.execution.worker import DurableWorker


@pytest.mark.asyncio
async def test_worker_executes_matching_domain_and_persists_result() -> None:
    store = InMemoryDurableJobStore()
    submitted = await store.submit(
        JobSpec(idempotency_key="oss-1", domain="oss", payload={"ticket": "INC-1"})
    )

    async def handler(job):
        return {"handled": job.spec.payload["ticket"]}

    worker = DurableWorker(store=store, worker_id="oss-a", handlers={"oss": handler})
    completed = await worker.run_once()

    assert completed is not None
    assert completed.job_id == submitted.job.job_id
    assert completed.status is JobStatus.SUCCEEDED
    assert completed.result == {"handled": "INC-1"}


@pytest.mark.asyncio
async def test_worker_does_not_claim_unhandled_domain() -> None:
    store = InMemoryDurableJobStore()
    submitted = await store.submit(JobSpec(idempotency_key="billing-1", domain="billing", payload={}))

    async def oss_handler(job):
        return job.job_id

    worker = DurableWorker(store=store, worker_id="oss-a", handlers={"oss": oss_handler})

    assert await worker.run_once() is None
    untouched = await store.get(submitted.job.job_id)
    assert untouched.status is JobStatus.QUEUED
    assert untouched.attempt == 0


@pytest.mark.asyncio
async def test_worker_failure_is_sanitized_and_scheduled_for_retry() -> None:
    store = InMemoryDurableJobStore()
    submitted = await store.submit(
        JobSpec(
            idempotency_key="retry-1",
            domain="oss",
            payload={},
            retry=RetryPolicy(max_attempts=2, initial_backoff_seconds=60, max_backoff_seconds=60),
        )
    )

    async def failing_handler(job):
        raise RuntimeError(f"sensitive-provider-value-{job.job_id}")

    worker = DurableWorker(store=store, worker_id="oss-a", handlers={"oss": failing_handler})
    failed = await worker.run_once()

    assert failed is not None
    assert failed.job_id == submitted.job.job_id
    assert failed.status is JobStatus.RETRY_WAIT
    assert failed.last_error == "RuntimeError"
    assert "sensitive-provider-value" not in failed.last_error


@pytest.mark.asyncio
async def test_worker_renews_lease_during_long_handler() -> None:
    store = InMemoryDurableJobStore()
    submitted = await store.submit(JobSpec(idempotency_key="slow-1", domain="oss", payload={}))
    heartbeat_calls = 0
    original_heartbeat = store.heartbeat

    async def counting_heartbeat(**kwargs):
        nonlocal heartbeat_calls
        heartbeat_calls += 1
        return await original_heartbeat(**kwargs)

    store.heartbeat = counting_heartbeat  # type: ignore[method-assign]

    async def slow_handler(job):
        await asyncio.sleep(0.04)
        return job.job_id

    worker = DurableWorker(
        store=store,
        worker_id="oss-a",
        handlers={"oss": slow_handler},
        lease_seconds=0.05,
        heartbeat_interval_seconds=0.01,
    )
    completed = await worker.run_once()

    assert completed is not None
    assert completed.job_id == submitted.job.job_id
    assert completed.status is JobStatus.SUCCEEDED
    assert heartbeat_calls >= 2


@pytest.mark.asyncio
async def test_business_cancellation_requested_during_execution_blocks_commit() -> None:
    store = InMemoryDurableJobStore()
    submitted = await store.submit(JobSpec(idempotency_key="cancel-1", domain="oss", payload={}))
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(job):
        started.set()
        await release.wait()
        return "must-not-commit"

    worker = DurableWorker(store=store, worker_id="oss-a", handlers={"oss": handler})
    task = asyncio.create_task(worker.run_once())
    await started.wait()

    requested = await store.request_cancel(submitted.job.job_id)
    assert requested.cancel_requested is True
    release.set()

    completed = await task
    assert completed is not None
    assert completed.status is JobStatus.CANCELLED
    assert completed.result is None


@pytest.mark.asyncio
async def test_worker_shutdown_leaves_job_recoverable_instead_of_cancelling_business_job() -> None:
    store = InMemoryDurableJobStore()
    submitted = await store.submit(JobSpec(idempotency_key="shutdown-1", domain="oss", payload={}))
    started = asyncio.Event()

    async def handler(job):
        started.set()
        await asyncio.Event().wait()

    worker = DurableWorker(
        store=store,
        worker_id="oss-a",
        handlers={"oss": handler},
        lease_seconds=1,
        heartbeat_interval_seconds=0.2,
    )
    task = asyncio.create_task(worker.run_once())
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    interrupted = await store.get(submitted.job.job_id)
    assert interrupted.status is JobStatus.RUNNING
    assert interrupted.cancel_requested is False
