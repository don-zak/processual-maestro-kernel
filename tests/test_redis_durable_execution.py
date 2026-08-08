import asyncio
import os
import uuid

import pytest
import pytest_asyncio
import redis.asyncio as redis

from processual_api.execution.durable import (
    ExecutionPriority,
    JobLeaseLostError,
    JobSpec,
    JobStatus,
    RetryPolicy,
)
from processual_api.execution.redis_store import RedisDurableJobStore


@pytest_asyncio.fixture
async def redis_client():
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    await client.ping()
    yield client
    await client.aclose()


def store(redis_client) -> RedisDurableJobStore:
    return RedisDurableJobStore(redis_client, prefix=f"test:durable:{uuid.uuid4().hex}")


def spec(
    key: str,
    *,
    domain: str = "network",
    priority: ExecutionPriority = ExecutionPriority.NORMAL,
    retry: RetryPolicy | None = None,
    deadline_at: float | None = None,
) -> JobSpec:
    return JobSpec(
        idempotency_key=key,
        domain=domain,
        payload={"ticket": key},
        priority=priority,
        retry=retry or RetryPolicy(max_attempts=3, initial_backoff_seconds=0.01, max_backoff_seconds=0.02),
        deadline_at=deadline_at,
    )


@pytest.mark.asyncio
async def test_concurrent_idempotent_submit_creates_one_job(redis_client) -> None:
    shared = store(redis_client)
    request = spec("same-operation")

    results = await asyncio.gather(*(shared.submit(request) for _ in range(12)))

    assert len({result.job.job_id for result in results}) == 1
    assert sum(result.created for result in results) == 1


@pytest.mark.asyncio
async def test_two_workers_cannot_claim_same_job(redis_client) -> None:
    prefix = f"test:durable:{uuid.uuid4().hex}"
    first = RedisDurableJobStore(redis_client, prefix=prefix)
    second = RedisDurableJobStore(redis_client, prefix=prefix)
    submitted = await first.submit(spec("claim-once"))

    claims = await asyncio.gather(
        first.claim(worker_id="worker-a", lease_seconds=1),
        second.claim(worker_id="worker-b", lease_seconds=1),
    )

    claimed = [job for job in claims if job is not None]
    assert len(claimed) == 1
    assert claimed[0].job_id == submitted.job.job_id
    assert claimed[0].attempt == 1


@pytest.mark.asyncio
async def test_priority_and_domain_filtering_are_shared(redis_client) -> None:
    shared = store(redis_client)
    await shared.submit(spec("batch", domain="billing", priority=ExecutionPriority.BATCH))
    emergency = await shared.submit(
        spec("alarm", domain="network", priority=ExecutionPriority.EMERGENCY)
    )
    await shared.submit(
        spec("interactive", domain="network", priority=ExecutionPriority.INTERACTIVE)
    )

    claimed = await shared.claim(
        worker_id="noc-worker",
        lease_seconds=1,
        domains=("network",),
    )

    assert claimed is not None
    assert claimed.job_id == emergency.job.job_id
    assert claimed.spec.domain == "network"


@pytest.mark.asyncio
async def test_expired_worker_lease_is_recovered_and_reclaimed(redis_client) -> None:
    shared = store(redis_client)
    submitted = await shared.submit(spec("recover"))
    first_claim = await shared.claim(worker_id="worker-a", lease_seconds=0.05)
    assert first_claim is not None

    await asyncio.sleep(0.08)
    assert await shared.recover_expired_leases() == 1

    second_claim = await shared.claim(worker_id="worker-b", lease_seconds=1)
    assert second_claim is not None
    assert second_claim.job_id == submitted.job.job_id
    assert second_claim.attempt == 2
    assert second_claim.worker_id == "worker-b"


@pytest.mark.asyncio
async def test_heartbeat_keeps_job_out_of_recovery(redis_client) -> None:
    shared = store(redis_client)
    await shared.submit(spec("heartbeat"))
    claimed = await shared.claim(worker_id="worker-a", lease_seconds=0.12)
    assert claimed is not None and claimed.lease_token is not None

    await asyncio.sleep(0.06)
    renewed = await shared.heartbeat(
        job_id=claimed.job_id,
        worker_id="worker-a",
        lease_token=claimed.lease_token,
        lease_seconds=0.15,
    )
    await asyncio.sleep(0.08)

    assert renewed.lease_expires_at is not None
    assert await shared.recover_expired_leases() == 0
    assert (await shared.get(claimed.job_id)).status is JobStatus.RUNNING


@pytest.mark.asyncio
async def test_stale_worker_cannot_complete_after_recovery(redis_client) -> None:
    shared = store(redis_client)
    await shared.submit(spec("stale-owner"))
    old = await shared.claim(worker_id="worker-a", lease_seconds=0.05)
    assert old is not None and old.lease_token is not None

    await asyncio.sleep(0.08)
    assert await shared.recover_expired_leases() == 1
    current = await shared.claim(worker_id="worker-b", lease_seconds=1)
    assert current is not None

    with pytest.raises(JobLeaseLostError):
        await shared.succeed(
            job_id=old.job_id,
            worker_id="worker-a",
            lease_token=old.lease_token,
            result={"unsafe": True},
        )


@pytest.mark.asyncio
async def test_failure_retry_and_success_survive_store_instances(redis_client) -> None:
    prefix = f"test:durable:{uuid.uuid4().hex}"
    first = RedisDurableJobStore(redis_client, prefix=prefix)
    second = RedisDurableJobStore(redis_client, prefix=prefix)
    await first.submit(spec("retry"))
    claimed = await first.claim(worker_id="worker-a", lease_seconds=1)
    assert claimed is not None and claimed.lease_token is not None

    failed = await first.fail(
        job_id=claimed.job_id,
        worker_id="worker-a",
        lease_token=claimed.lease_token,
        error="TimeoutError",
    )
    assert failed.status is JobStatus.RETRY_WAIT

    await asyncio.sleep(0.03)
    retried = await second.claim(worker_id="worker-b", lease_seconds=1)
    assert retried is not None and retried.lease_token is not None
    completed = await second.succeed(
        job_id=retried.job_id,
        worker_id="worker-b",
        lease_token=retried.lease_token,
        result={"ok": True},
    )

    assert completed.status is JobStatus.SUCCEEDED
    assert completed.result == {"ok": True}
    assert (await first.get(retried.job_id)).status is JobStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_queued_cancellation_removes_job_from_claimable_queue(redis_client) -> None:
    shared = store(redis_client)
    submitted = await shared.submit(spec("cancel"))

    cancelled = await shared.request_cancel(submitted.job.job_id)

    assert cancelled.status is JobStatus.CANCELLED
    assert cancelled.cancel_requested is True
    assert await shared.claim(worker_id="worker-a", lease_seconds=1) is None


@pytest.mark.asyncio
async def test_expired_queued_deadline_is_persisted_as_failed(redis_client) -> None:
    shared = store(redis_client)
    seconds, micros = await redis_client.time()
    redis_now = float(seconds) + float(micros) / 1_000_000
    submitted = await shared.submit(spec("expired-queued", deadline_at=redis_now - 1))

    assert await shared.claim(worker_id="worker-a", lease_seconds=1) is None

    persisted = await shared.get(submitted.job.job_id)
    assert persisted.status is JobStatus.FAILED
    assert persisted.last_error == "deadline_exceeded"


@pytest.mark.asyncio
async def test_heartbeat_persists_deadline_failure_before_losing_lease(redis_client) -> None:
    shared = store(redis_client)
    seconds, micros = await redis_client.time()
    redis_now = float(seconds) + float(micros) / 1_000_000
    submitted = await shared.submit(spec("deadline-heartbeat", deadline_at=redis_now + 0.08))
    claimed = await shared.claim(worker_id="worker-a", lease_seconds=0.4)
    assert claimed is not None and claimed.lease_token is not None

    await asyncio.sleep(0.11)
    with pytest.raises(JobLeaseLostError, match="deadline expired"):
        await shared.heartbeat(
            job_id=claimed.job_id,
            worker_id="worker-a",
            lease_token=claimed.lease_token,
            lease_seconds=0.4,
        )

    persisted = await shared.get(submitted.job.job_id)
    assert persisted.status is JobStatus.FAILED
    assert persisted.last_error == "deadline_exceeded"
    assert persisted.worker_id is None
    assert persisted.lease_token is None
