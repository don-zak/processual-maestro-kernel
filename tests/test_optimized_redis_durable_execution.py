import asyncio
import os
import uuid

import pytest
import redis.asyncio as redis

from processual_api.execution.durable import ExecutionPriority, JobSpec
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
async def test_optimized_claim_preserves_priority_and_domain_filtering() -> None:
    client = redis.from_url(
        os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    prefix = f"{{optimized-priority-{uuid.uuid4().hex}}}"
    store = OptimizedRedisDurableJobStore(client, prefix=prefix)
    try:
        await store.submit(
            JobSpec(
                idempotency_key="batch",
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


def test_claim_window_must_be_positive() -> None:
    with pytest.raises(ValueError, match="claim_window"):
        OptimizedRedisDurableJobStore(object(), claim_window=0)
