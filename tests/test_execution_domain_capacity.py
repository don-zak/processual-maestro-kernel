import asyncio
import os
import uuid

import pytest
import pytest_asyncio
import redis.asyncio as redis

from processual_api.execution.capacity import (
    DomainCapacityController,
    DomainCapacityPolicy,
    DomainCapacitySaturatedError,
    InMemoryDomainCapacityBackend,
    RedisDomainCapacityBackend,
)
from processual_api.execution.durable import ExecutionPriority, JobSpec, JobStatus
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


def policy() -> DomainCapacityPolicy:
    return DomainCapacityPolicy(
        global_limit=4,
        domain_limits={"network": 4, "billing": 1},
        emergency_reserve=1,
    )


def controller(backend, *, wait_seconds: float = 0) -> DomainCapacityController:
    return DomainCapacityController(
        backend=backend,
        policy=policy(),
        lease_seconds=0.2,
        wait_seconds=wait_seconds,
        retry_seconds=0.01,
    )


def test_policy_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError):
        DomainCapacityPolicy(global_limit=0, domain_limits={"network": 1})
    with pytest.raises(ValueError):
        DomainCapacityPolicy(global_limit=2, domain_limits={"network": 1}, emergency_reserve=2)
    with pytest.raises(ValueError):
        DomainCapacityPolicy(global_limit=2, domain_limits={"network": 0})


@pytest.mark.asyncio
async def test_emergency_reserve_prevents_normal_work_from_consuming_last_slot() -> None:
    guard = controller(InMemoryDomainCapacityBackend())
    reservations = [
        await guard.acquire(domain="network", priority=ExecutionPriority.NORMAL)
        for _ in range(3)
    ]

    with pytest.raises(DomainCapacitySaturatedError, match="emergency_reserve"):
        await guard.acquire(domain="network", priority=ExecutionPriority.NORMAL)

    emergency = await guard.acquire(domain="network", priority=ExecutionPriority.EMERGENCY)
    assert emergency.priority is ExecutionPriority.EMERGENCY

    for reservation in [*reservations, emergency]:
        await guard.release(reservation)


@pytest.mark.asyncio
async def test_domain_limit_isolated_from_remaining_global_capacity() -> None:
    guard = controller(InMemoryDomainCapacityBackend())
    billing = await guard.acquire(domain="billing", priority=ExecutionPriority.NORMAL)

    with pytest.raises(DomainCapacitySaturatedError, match="domain"):
        await guard.acquire(domain="billing", priority=ExecutionPriority.NORMAL)

    network = await guard.acquire(domain="network", priority=ExecutionPriority.NORMAL)
    assert network.domain == "network"

    await guard.release(billing)
    await guard.release(network)


@pytest.mark.asyncio
async def test_release_immediately_returns_capacity() -> None:
    guard = controller(InMemoryDomainCapacityBackend())
    first = await guard.acquire(domain="billing", priority=ExecutionPriority.NORMAL)
    await guard.release(first)

    replacement = await guard.acquire(domain="billing", priority=ExecutionPriority.NORMAL)
    assert replacement.lease_id != first.lease_id


@pytest.mark.asyncio
async def test_redis_capacity_is_shared_across_controllers(redis_client) -> None:
    prefix = f"{{test-durable-capacity-{uuid.uuid4().hex}}}"
    first = controller(RedisDomainCapacityBackend(redis_client, prefix=prefix))
    second = controller(RedisDomainCapacityBackend(redis_client, prefix=prefix))

    reservations = [
        await first.acquire(domain="network", priority=ExecutionPriority.NORMAL)
        for _ in range(3)
    ]

    with pytest.raises(DomainCapacitySaturatedError, match="emergency_reserve"):
        await second.acquire(domain="network", priority=ExecutionPriority.INTERACTIVE)

    emergency = await second.acquire(domain="network", priority=ExecutionPriority.EMERGENCY)
    assert emergency.priority is ExecutionPriority.EMERGENCY

    for reservation in [*reservations, emergency]:
        await first.release(reservation)


@pytest.mark.asyncio
async def test_redis_domain_limit_is_shared_across_workers(redis_client) -> None:
    prefix = f"{{test-durable-capacity-{uuid.uuid4().hex}}}"
    first = controller(RedisDomainCapacityBackend(redis_client, prefix=prefix))
    second = controller(RedisDomainCapacityBackend(redis_client, prefix=prefix))
    billing = await first.acquire(domain="billing", priority=ExecutionPriority.NORMAL)

    with pytest.raises(DomainCapacitySaturatedError, match="domain"):
        await second.acquire(domain="billing", priority=ExecutionPriority.NORMAL)

    network = await second.acquire(domain="network", priority=ExecutionPriority.NORMAL)
    assert network.domain == "network"

    await first.release(billing)
    await second.release(network)


@pytest.mark.asyncio
async def test_redis_expired_capacity_lease_self_recovers(redis_client) -> None:
    prefix = f"{{test-durable-capacity-{uuid.uuid4().hex}}}"
    short = DomainCapacityController(
        backend=RedisDomainCapacityBackend(redis_client, prefix=prefix),
        policy=DomainCapacityPolicy(
            global_limit=2,
            domain_limits={"billing": 1},
            emergency_reserve=0,
        ),
        lease_seconds=0.05,
        wait_seconds=0,
        retry_seconds=0.01,
    )
    first = await short.acquire(domain="billing", priority=ExecutionPriority.NORMAL)

    await asyncio.sleep(0.08)
    second = await short.acquire(domain="billing", priority=ExecutionPriority.NORMAL)

    assert second.lease_id != first.lease_id


@pytest.mark.asyncio
async def test_two_redis_workers_share_capacity_without_burning_attempts(redis_client) -> None:
    store_prefix = f"test:durable-worker:{uuid.uuid4().hex}"
    capacity_prefix = f"{{test-worker-capacity-{uuid.uuid4().hex}}}"
    first_store = RedisDurableJobStore(redis_client, prefix=store_prefix)
    second_store = RedisDurableJobStore(redis_client, prefix=store_prefix)
    capacity_policy = DomainCapacityPolicy(
        global_limit=1,
        domain_limits={"network": 1},
        emergency_reserve=0,
    )
    first_capacity = DomainCapacityController(
        backend=RedisDomainCapacityBackend(redis_client, prefix=capacity_prefix),
        policy=capacity_policy,
        lease_seconds=0.5,
        wait_seconds=0,
        retry_seconds=0.01,
    )
    second_capacity = DomainCapacityController(
        backend=RedisDomainCapacityBackend(redis_client, prefix=capacity_prefix),
        policy=capacity_policy,
        lease_seconds=0.5,
        wait_seconds=0,
        retry_seconds=0.01,
    )
    first_job = await first_store.submit(
        JobSpec(idempotency_key="network-a", domain="network", payload={})
    )
    second_job = await first_store.submit(
        JobSpec(idempotency_key="network-b", domain="network", payload={})
    )
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocking_handler(job):
        started.set()
        await release.wait()
        return job.spec.idempotency_key

    async def fast_handler(job):
        return job.spec.idempotency_key

    first_worker = DurableWorker(
        store=first_store,
        worker_id="network-a",
        handlers={"network": blocking_handler},
        capacity=first_capacity,
        capacity_heartbeat_interval_seconds=0.1,
    )
    second_worker = DurableWorker(
        store=second_store,
        worker_id="network-b",
        handlers={"network": fast_handler},
        capacity=second_capacity,
        capacity_heartbeat_interval_seconds=0.1,
        capacity_requeue_delay_seconds=0,
    )

    first_task = asyncio.create_task(first_worker.run_once())
    await started.wait()

    requeued = await second_worker.run_once()
    assert requeued is not None
    assert requeued.job_id == second_job.job.job_id
    assert requeued.status is JobStatus.QUEUED
    assert requeued.attempt == 0

    release.set()
    first_completed = await first_task
    assert first_completed is not None
    assert first_completed.job_id == first_job.job.job_id
    assert first_completed.status is JobStatus.SUCCEEDED

    second_completed = await second_worker.run_once()
    assert second_completed is not None
    assert second_completed.job_id == second_job.job.job_id
    assert second_completed.status is JobStatus.SUCCEEDED
    assert second_completed.attempt == 1
