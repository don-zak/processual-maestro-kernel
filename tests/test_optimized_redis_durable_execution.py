import asyncio
import os
import time
import uuid

import pytest
import redis.asyncio as redis

from processual_api.execution.durable import ExecutionPriority, JobSpec, JobStatus, RetryPolicy
from processual_api.execution.redis_store_optimized import OptimizedRedisDurableJobStore


@pytest.mark.asyncio
async def test_many_workers_claim_distinct_jobs_without_duplicates() -> None:
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    prefix = f"{{optimized-claim-{uuid.uuid4().hex}}}"
    stores = [OptimizedRedisDurableJobStore(client, prefix=prefix) for _ in range(8)]
    try:
        submitted = []
        for index in range(8):
            result = await stores[0].submit(
                JobSpec(
                    idempotency_key=f"claim-{index}",
                    domain="network",
                    payload={"index": index},
                )
            )
            submitted.append(result.job.job_id)

        claims = await asyncio.gather(
            *(
                store.claim(worker_id=f"worker-{index}", lease_seconds=1)
                for index, store in enumerate(stores)
            )
        )
        claimed_ids = [job.job_id for job in claims if job is not None]

        assert len(claimed_ids) == 8
        assert len(set(claimed_ids)) == 8
        assert set(claimed_ids) == set(submitted)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_atomic_claim_expires_deadline_before_claiming_next_job() -> None:
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    prefix = f"{{optimized-deadline-{uuid.uuid4().hex}}}"
    store = OptimizedRedisDurableJobStore(client, prefix=prefix)
    try:
        expired = await store.submit(
            JobSpec(
                idempotency_key="expired",
                domain="network",
                payload={},
                priority=ExecutionPriority.EMERGENCY,
                deadline_at=time.time() - 1,
            )
        )
        ready = await store.submit(
            JobSpec(
                idempotency_key="ready",
                domain="network",
                payload={},
                priority=ExecutionPriority.INTERACTIVE,
            )
        )

        claimed = await store.claim(worker_id="worker", lease_seconds=1)
        expired_job = await store.get(expired.job.job_id)

        assert expired_job.status is JobStatus.FAILED
        assert expired_job.last_error == "deadline_exceeded"
        assert claimed is not None
        assert claimed.job_id == ready.job.job_id
        assert claimed.attempt == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_atomic_claim_preserves_priority_order() -> None:
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    prefix = f"{{optimized-atomic-priority-{uuid.uuid4().hex}}}"
    store = OptimizedRedisDurableJobStore(client, prefix=prefix, candidate_window=2)
    try:
        for index in range(20):
            await store.submit(
                JobSpec(
                    idempotency_key=f"batch-{index}",
                    domain="billing",
                    payload={},
                    priority=ExecutionPriority.BATCH,
                )
            )
        emergency = await store.submit(
            JobSpec(
                idempotency_key="alarm",
                domain="network",
                payload={},
                priority=ExecutionPriority.EMERGENCY,
            )
        )

        claimed = await store.claim(worker_id="noc-worker", lease_seconds=1)

        assert claimed is not None
        assert claimed.job_id == emergency.job.job_id
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_optimized_claim_preserves_priority_and_domain_filtering() -> None:
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    prefix = f"{{optimized-priority-{uuid.uuid4().hex}}}"
    store = OptimizedRedisDurableJobStore(client, prefix=prefix, candidate_window=2)
    try:
        for index in range(20):
            await store.submit(
                JobSpec(
                    idempotency_key=f"batch-{index}",
                    domain="billing",
                    payload={},
                    priority=ExecutionPriority.BATCH,
                )
            )
        emergency = await store.submit(
            JobSpec(
                idempotency_key="alarm",
                domain="network",
                payload={},
                priority=ExecutionPriority.EMERGENCY,
            )
        )
        await store.submit(
            JobSpec(
                idempotency_key="interactive",
                domain="network",
                payload={},
                priority=ExecutionPriority.INTERACTIVE,
            )
        )

        claimed = await store.claim(
            worker_id="noc-worker",
            lease_seconds=1,
            domains=("network",),
        )

        assert claimed is not None
        assert claimed.job_id == emergency.job.job_id
        assert claimed.spec.domain == "network"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_non_hash_tag_prefix_uses_safe_watch_fallback() -> None:
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    store = OptimizedRedisDurableJobStore(
        client,
        prefix=f"optimized-fallback-{uuid.uuid4().hex}",
    )
    try:
        submitted = await store.submit(
            JobSpec(idempotency_key="fallback", domain="network", payload={})
        )
        claimed = await store.claim(worker_id="worker", lease_seconds=1)

        assert claimed is not None
        assert claimed.job_id == submitted.job.job_id
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_priority_index_tracks_retry_cancel_and_recovery() -> None:
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    prefix = f"{{optimized-index-{uuid.uuid4().hex}}}"
    store = OptimizedRedisDurableJobStore(client, prefix=prefix)
    try:
        retry_job = await store.submit(
            JobSpec(
                idempotency_key="retry",
                domain="network",
                payload={},
                priority=ExecutionPriority.INTERACTIVE,
                retry=RetryPolicy(
                    max_attempts=3,
                    initial_backoff_seconds=0.01,
                    max_backoff_seconds=0.02,
                ),
            )
        )
        claimed = await store.claim(worker_id="worker-a", lease_seconds=1)
        assert claimed is not None and claimed.lease_token is not None
        retried = await store.fail(
            job_id=claimed.job_id,
            worker_id="worker-a",
            lease_token=claimed.lease_token,
            error="TimeoutError",
        )
        assert retried.status is JobStatus.RETRY_WAIT

        await asyncio.sleep(0.03)
        claimed_again = await store.claim(worker_id="worker-b", lease_seconds=0.05)
        assert claimed_again is not None
        assert claimed_again.job_id == retry_job.job.job_id
        await asyncio.sleep(0.08)
        assert await store.recover_expired_leases() == 1
        recovered = await store.claim(worker_id="worker-c", lease_seconds=1)
        assert recovered is not None
        assert recovered.job_id == retry_job.job.job_id

        cancelled = await store.submit(
            JobSpec(
                idempotency_key="cancel",
                domain="billing",
                payload={},
                priority=ExecutionPriority.BATCH,
            )
        )
        cancelled_job = await store.request_cancel(cancelled.job.job_id)
        assert cancelled_job.status is JobStatus.CANCELLED
    finally:
        await client.aclose()


def test_candidate_window_must_be_positive() -> None:
    with pytest.raises(ValueError, match="candidate_window"):
        OptimizedRedisDurableJobStore(object(), candidate_window=0)
