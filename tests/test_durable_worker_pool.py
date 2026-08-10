import asyncio

import pytest

from processual_api.execution.durable import InMemoryDurableJobStore, JobSpec, JobStatus
from processual_api.execution.pool import DurableWorkerPool, DurableWorkerPoolPolicy
from processual_api.execution.worker import DurableWorker


@pytest.mark.asyncio
async def test_pool_continuously_drains_jobs_and_stops_cleanly() -> None:
    store = InMemoryDurableJobStore()
    for index in range(3):
        await store.submit(JobSpec(idempotency_key=f"job-{index}", domain="oss", payload={"n": index}))

    async def handler(job):
        return job.spec.payload["n"] * 2

    worker = DurableWorker(store=store, worker_id="oss-a", handlers={"oss": handler})
    pool = DurableWorkerPool(
        store=store,
        workers=[worker],
        policy=DurableWorkerPoolPolicy(idle_poll_seconds=0.005, recovery_interval_seconds=0.02),
    )

    await pool.start()
    for _ in range(100):
        jobs = [await store.get(job_id) for job_id in list(store._jobs)]  # type: ignore[attr-defined]
        if all(job.status is JobStatus.SUCCEEDED for job in jobs):
            break
        await asyncio.sleep(0.005)
    await pool.stop(graceful_timeout_seconds=0.2)

    jobs = [await store.get(job_id) for job_id in list(store._jobs)]  # type: ignore[attr-defined]
    assert all(job.status is JobStatus.SUCCEEDED for job in jobs)
    assert pool.running is False


@pytest.mark.asyncio
async def test_pool_recovery_loop_requeues_expired_worker_claim_for_replacement() -> None:
    store = InMemoryDurableJobStore()
    submitted = await store.submit(JobSpec(idempotency_key="recover-me", domain="oss", payload={}))

    claimed = await store.claim(worker_id="dead-worker", lease_seconds=0.03)
    assert claimed is not None

    async def replacement_handler(job):
        return {"recovered": job.job_id}

    replacement = DurableWorker(
        store=store,
        worker_id="replacement",
        handlers={"oss": replacement_handler},
        lease_seconds=0.05,
        heartbeat_interval_seconds=0.01,
    )
    pool = DurableWorkerPool(
        store=store,
        workers=[replacement],
        policy=DurableWorkerPoolPolicy(idle_poll_seconds=0.005, recovery_interval_seconds=0.01),
    )

    await pool.start()
    for _ in range(100):
        current = await store.get(submitted.job.job_id)
        if current.status is JobStatus.SUCCEEDED:
            break
        await asyncio.sleep(0.005)
    await pool.stop(graceful_timeout_seconds=0.2)

    recovered = await store.get(submitted.job.job_id)
    assert recovered.status is JobStatus.SUCCEEDED
    assert recovered.attempt == 2
    assert recovered.result == {"recovered": submitted.job.job_id}


@pytest.mark.asyncio
async def test_pool_forced_shutdown_leaves_running_job_for_lease_recovery() -> None:
    store = InMemoryDurableJobStore()
    submitted = await store.submit(JobSpec(idempotency_key="shutdown-running", domain="oss", payload={}))
    started = asyncio.Event()

    async def blocked_handler(job):
        started.set()
        await asyncio.Event().wait()

    worker = DurableWorker(
        store=store,
        worker_id="oss-a",
        handlers={"oss": blocked_handler},
        lease_seconds=0.05,
        heartbeat_interval_seconds=0.01,
    )
    pool = DurableWorkerPool(
        store=store,
        workers=[worker],
        policy=DurableWorkerPoolPolicy(idle_poll_seconds=0.005, recovery_interval_seconds=0.01),
    )

    await pool.start()
    await started.wait()
    await pool.stop(graceful_timeout_seconds=0)

    interrupted = await store.get(submitted.job.job_id)
    assert interrupted.status is JobStatus.RUNNING
    assert interrupted.cancel_requested is False

    await asyncio.sleep(0.06)
    assert await store.recover_expired_leases() == 1
    recovered = await store.get(submitted.job.job_id)
    assert recovered.status is JobStatus.QUEUED


@pytest.mark.asyncio
async def test_pool_isolates_worker_errors_and_keeps_other_workers_alive() -> None:
    store = InMemoryDurableJobStore()
    first = await store.submit(JobSpec(idempotency_key="bad", domain="bad", payload={}))
    second = await store.submit(JobSpec(idempotency_key="good", domain="good", payload={}))
    seen_errors: list[str] = []

    async def bad_handler(job):
        raise RuntimeError("boom")

    async def good_handler(job):
        return "ok"

    bad = DurableWorker(store=store, worker_id="bad-worker", handlers={"bad": bad_handler})
    good = DurableWorker(store=store, worker_id="good-worker", handlers={"good": good_handler})
    pool = DurableWorkerPool(
        store=store,
        workers=[bad, good],
        policy=DurableWorkerPoolPolicy(idle_poll_seconds=0.005, recovery_interval_seconds=0.02),
        on_worker_error=lambda exc: seen_errors.append(type(exc).__name__),
    )

    await pool.start()
    for _ in range(100):
        good_job = await store.get(second.job.job_id)
        bad_job = await store.get(first.job.job_id)
        if good_job.status is JobStatus.SUCCEEDED and bad_job.status is JobStatus.RETRY_WAIT:
            break
        await asyncio.sleep(0.005)
    await pool.stop(graceful_timeout_seconds=0.2)

    assert (await store.get(second.job.job_id)).status is JobStatus.SUCCEEDED
    assert (await store.get(first.job.job_id)).status is JobStatus.RETRY_WAIT
    assert seen_errors == []


def test_pool_policy_and_construction_validate_inputs() -> None:
    with pytest.raises(ValueError):
        DurableWorkerPoolPolicy(idle_poll_seconds=0)
    with pytest.raises(ValueError):
        DurableWorkerPoolPolicy(recovery_interval_seconds=0)
    with pytest.raises(ValueError):
        DurableWorkerPool(store=InMemoryDurableJobStore(), workers=[])
