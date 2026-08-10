import asyncio
import os
import time
import uuid

import pytest
import redis.asyncio as redis

from processual_api.execution.durable import ExecutionPriority, JobSpec, JobStatus, RetryPolicy
from processual_api.execution.redis_index_repair import rebuild_priority_indexes
from processual_api.execution.redis_store import RedisDurableJobStore
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
async def test_parallel_lease_completions_remain_independent() -> None:
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    prefix = f"{{optimized-complete-{uuid.uuid4().hex}}}"
    stores = [OptimizedRedisDurableJobStore(client, prefix=prefix) for _ in range(8)]
    try:
        for index in range(8):
            await stores[0].submit(
                JobSpec(
                    idempotency_key=f"complete-{index}",
                    domain="network",
                    payload={"index": index},
                )
            )

        claims = await asyncio.gather(
            *(
                store.claim(worker_id=f"worker-{index}", lease_seconds=2)
                for index, store in enumerate(stores)
            )
        )
        assert all(claim is not None and claim.lease_token is not None for claim in claims)

        completed = await asyncio.gather(
            *(
                stores[index].succeed(
                    job_id=claim.job_id,
                    worker_id=f"worker-{index}",
                    lease_token=claim.lease_token,
                    result={"worker": index},
                )
                for index, claim in enumerate(claims)
                if claim is not None and claim.lease_token is not None
            )
        )

        assert len(completed) == 8
        assert all(job.status is JobStatus.SUCCEEDED for job in completed)
        assert all(job.attempt == 1 for job in completed)
        assert len({job.job_id for job in completed}) == 8
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


@pytest.mark.asyncio
async def test_rebuild_priority_indexes_makes_legacy_jobs_claimable() -> None:
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    prefix = f"{{optimized-repair-legacy-{uuid.uuid4().hex}}}"
    legacy = RedisDurableJobStore(client, prefix=prefix)
    optimized = OptimizedRedisDurableJobStore(client, prefix=prefix)
    try:
        legacy_job = await legacy.submit(
            JobSpec(
                idempotency_key="legacy",
                domain="network",
                payload={},
                priority=ExecutionPriority.EMERGENCY,
            )
        )
        assert await optimized.claim(worker_id="before-repair", lease_seconds=1) is None

        result = await rebuild_priority_indexes(client, prefix=prefix, batch_size=1)
        claimed = await optimized.claim(worker_id="after-repair", lease_seconds=1)

        assert result.scanned_shared == 1
        assert result.indexed == 1
        assert result.removed_stale_shared == 0
        assert claimed is not None
        assert claimed.job_id == legacy_job.job.job_id
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rebuild_priority_indexes_repairs_wrong_and_stale_membership() -> None:
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    prefix = f"{{optimized-repair-stale-{uuid.uuid4().hex}}}"
    store = OptimizedRedisDurableJobStore(client, prefix=prefix)
    try:
        submitted = await store.submit(
            JobSpec(
                idempotency_key="repair",
                domain="network",
                payload={},
                priority=ExecutionPriority.INTERACTIVE,
            )
        )
        job_id = submitted.job.job_id
        correct_key = f"{prefix}:queue:p{int(ExecutionPriority.INTERACTIVE)}"
        wrong_key = f"{prefix}:queue:p{int(ExecutionPriority.BATCH)}"
        stale_id = "missing-job"
        await client.zrem(correct_key, job_id)
        await client.zadd(wrong_key, {job_id: 0.0, stale_id: 0.0})

        first = await rebuild_priority_indexes(client, prefix=prefix)
        second = await rebuild_priority_indexes(client, prefix=prefix)

        assert await client.zscore(correct_key, job_id) is not None
        assert await client.zscore(wrong_key, job_id) is None
        assert await client.zscore(wrong_key, stale_id) is None
        assert first.indexed == 1
        assert first.removed_stale_priority == 1
        assert second.indexed == 1
        assert second.removed_stale_priority == 0
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rebuild_priority_indexes_removes_non_queueable_shared_entries() -> None:
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    prefix = f"{{optimized-repair-terminal-{uuid.uuid4().hex}}}"
    store = OptimizedRedisDurableJobStore(client, prefix=prefix)
    try:
        submitted = await store.submit(
            JobSpec(idempotency_key="terminal", domain="network", payload={})
        )
        claimed = await store.claim(worker_id="worker", lease_seconds=1)
        assert claimed is not None and claimed.lease_token is not None
        await store.succeed(
            job_id=claimed.job_id,
            worker_id="worker",
            lease_token=claimed.lease_token,
            result={"ok": True},
        )
        await client.zadd(f"{prefix}:queue", {submitted.job.job_id: 0.0})

        result = await rebuild_priority_indexes(client, prefix=prefix)

        assert result.removed_stale_shared == 1
        assert await client.zscore(f"{prefix}:queue", submitted.job.job_id) is None
    finally:
        await client.aclose()


def test_rebuild_priority_indexes_requires_positive_batch_size() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        asyncio.run(rebuild_priority_indexes(object(), batch_size=0))


def test_candidate_window_must_be_positive() -> None:
    with pytest.raises(ValueError, match="candidate_window"):
        OptimizedRedisDurableJobStore(object(), candidate_window=0)
