"""Explicit repair utilities for optimized Redis durable-job indexes.

The optimized store intentionally keeps compatibility repair out of its hot
claim path. Operators can run this idempotent repair before promoting an
existing Redis prefix that may contain jobs written by RedisDurableJobStore.
"""

from __future__ import annotations

from dataclasses import dataclass

from .durable import ExecutionPriority, JobStatus
from .redis_store import RedisDurableJobStore

_PRIORITY_ORDER = tuple(sorted(ExecutionPriority, key=int))
_QUEUED = {JobStatus.QUEUED, JobStatus.RETRY_WAIT}


@dataclass(frozen=True, slots=True)
class PriorityIndexRepairResult:
    scanned_shared: int
    indexed: int
    removed_stale_shared: int
    removed_stale_priority: int


async def rebuild_priority_indexes(
    redis_client,
    *,
    prefix: str = "maestro:durable",
    batch_size: int = 256,
) -> PriorityIndexRepairResult:
    """Repair optimized priority indexes from authoritative persisted job state.

    This is an explicit migration/maintenance operation, not part of claim().
    It is safe to run repeatedly. Shared queue membership plus each job hash are
    treated as authoritative; missing jobs and non-queueable states are removed
    while queued/retry-wait jobs are placed in exactly their current priority
    index using ``available_at`` as the score.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    store = RedisDurableJobStore(redis_client, prefix=prefix)
    normalized_prefix = store._prefix
    shared_key = store._queue_key
    priority_keys = {
        priority: f"{normalized_prefix}:queue:p{int(priority)}" for priority in _PRIORITY_ORDER
    }

    shared_ids = await redis_client.zrange(shared_key, 0, -1)
    scanned_shared = len(shared_ids)
    indexed = 0
    removed_stale_shared = 0

    for offset in range(0, len(shared_ids), batch_size):
        batch_ids = shared_ids[offset : offset + batch_size]
        async with redis_client.pipeline(transaction=False) as pipe:
            for job_id in batch_ids:
                pipe.hgetall(store._job_key(job_id))
            raw_jobs = await pipe.execute()

        async with redis_client.pipeline(transaction=False) as pipe:
            for job_id, raw in zip(batch_ids, raw_jobs, strict=True):
                if not raw:
                    pipe.zrem(shared_key, job_id)
                    for priority_key in priority_keys.values():
                        pipe.zrem(priority_key, job_id)
                    removed_stale_shared += 1
                    continue

                job = store._job_from_hash(raw)
                if job.status not in _QUEUED:
                    pipe.zrem(shared_key, job_id)
                    for priority_key in priority_keys.values():
                        pipe.zrem(priority_key, job_id)
                    removed_stale_shared += 1
                    continue

                pipe.zadd(shared_key, {job_id: job.available_at})
                for priority, priority_key in priority_keys.items():
                    if priority is job.spec.priority:
                        pipe.zadd(priority_key, {job_id: job.available_at})
                    else:
                        pipe.zrem(priority_key, job_id)
                indexed += 1
            await pipe.execute()

    removed_stale_priority = 0
    for priority_key in priority_keys.values():
        priority_ids = await redis_client.zrange(priority_key, 0, -1)
        for offset in range(0, len(priority_ids), batch_size):
            batch_ids = priority_ids[offset : offset + batch_size]
            async with redis_client.pipeline(transaction=False) as pipe:
                for job_id in batch_ids:
                    pipe.zscore(shared_key, job_id)
                shared_scores = await pipe.execute()
            stale_ids = [
                job_id
                for job_id, shared_score in zip(batch_ids, shared_scores, strict=True)
                if shared_score is None
            ]
            if stale_ids:
                await redis_client.zrem(priority_key, *stale_ids)
                removed_stale_priority += len(stale_ids)

    return PriorityIndexRepairResult(
        scanned_shared=scanned_shared,
        indexed=indexed,
        removed_stale_shared=removed_stale_shared,
        removed_stale_priority=removed_stale_priority,
    )
