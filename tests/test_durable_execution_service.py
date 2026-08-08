import asyncio

import pytest

from processual_api.execution.durable import InMemoryDurableJobStore, JobSpec, JobStatus
from processual_api.execution.pool import DurableWorkerPool, DurableWorkerPoolPolicy
from processual_api.execution.service import DurableExecutionService
from processual_api.execution.worker import DurableWorker


async def wait_for_status(service, job_id: str, expected: JobStatus, timeout: float = 1.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        job = await service.status(job_id)
        if job.status is expected:
            return job
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"job did not reach {expected}: {job.status}")
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_service_submit_execute_status_and_result() -> None:
    store = InMemoryDurableJobStore()

    async def handler(job):
        return {"ticket": job.spec.payload["ticket"], "handled": True}

    worker = DurableWorker(store=store, worker_id="network-a", handlers={"network": handler})
    pool = DurableWorkerPool(
        store=store,
        workers=[worker],
        policy=DurableWorkerPoolPolicy(idle_poll_seconds=0.01, recovery_interval_seconds=0.02),
    )
    service = DurableExecutionService(store=store, pool=pool)

    assert service.health().state == "stopped"
    submitted = await service.submit(
        JobSpec(
            idempotency_key="service-e2e-1",
            domain="network",
            payload={"ticket": "INC-900"},
        )
    )
    assert submitted.created is True
    assert (await service.status(submitted.job.job_id)).status is JobStatus.QUEUED

    await service.start()
    assert service.health().running is True
    completed = await wait_for_status(service, submitted.job.job_id, JobStatus.SUCCEEDED)

    assert completed.result == {"ticket": "INC-900", "handled": True}
    assert await service.result(submitted.job.job_id) == completed.result

    await service.stop()
    assert service.health().state == "stopped"


@pytest.mark.asyncio
async def test_service_cancel_prevents_queued_execution() -> None:
    store = InMemoryDurableJobStore()
    called = False

    async def handler(job):
        nonlocal called
        called = True
        return job.job_id

    worker = DurableWorker(store=store, worker_id="billing-a", handlers={"billing": handler})
    pool = DurableWorkerPool(store=store, workers=[worker])
    service = DurableExecutionService(store=store, pool=pool)
    submitted = await service.submit(
        JobSpec(idempotency_key="cancel-service", domain="billing", payload={})
    )

    cancelled = await service.cancel(submitted.job.job_id)
    assert cancelled.status is JobStatus.CANCELLED

    await service.start()
    await asyncio.sleep(0.05)
    await service.stop()

    assert called is False
    assert (await service.status(submitted.job.job_id)).status is JobStatus.CANCELLED


@pytest.mark.asyncio
async def test_service_is_idempotent_across_duplicate_submit() -> None:
    store = InMemoryDurableJobStore()
    service = DurableExecutionService(store=store)
    job_spec = JobSpec(idempotency_key="same-service-request", domain="oss", payload={"x": 1})

    first = await service.submit(job_spec)
    second = await service.submit(job_spec)

    assert first.created is True
    assert second.created is False
    assert first.job.job_id == second.job.job_id
    assert service.health().state == "not_configured"

    with pytest.raises(RuntimeError, match="worker pool is not configured"):
        await service.start()


@pytest.mark.asyncio
async def test_service_pool_recovers_expired_worker_lease_and_completes_job() -> None:
    store = InMemoryDurableJobStore()
    submitted = await store.submit(
        JobSpec(idempotency_key="service-recover", domain="network", payload={"alarm": "A-1"})
    )
    abandoned = await store.claim(worker_id="dead-worker", lease_seconds=0.03)
    assert abandoned is not None

    async def handler(job):
        return {"recovered": job.spec.payload["alarm"]}

    replacement = DurableWorker(
        store=store,
        worker_id="replacement",
        handlers={"network": handler},
        lease_seconds=0.2,
        heartbeat_interval_seconds=0.05,
    )
    pool = DurableWorkerPool(
        store=store,
        workers=[replacement],
        policy=DurableWorkerPoolPolicy(idle_poll_seconds=0.01, recovery_interval_seconds=0.01),
    )
    service = DurableExecutionService(store=store, pool=pool)

    await asyncio.sleep(0.04)
    await service.start()
    completed = await wait_for_status(service, submitted.job.job_id, JobStatus.SUCCEEDED)
    await service.stop()

    assert completed.attempt == 2
    assert completed.result == {"recovered": "A-1"}
