"""Contention-reduced Redis durable store.

This implementation preserves RedisDurableJobStore semantics while optimizing
only the claim path. It is opt-in until qualification proves it is safe to
promote as the default durable Redis store.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence

from redis.exceptions import WatchError

from .durable import ExecutionJob, JobStatus
from .redis_store import RedisDurableJobStore


class OptimizedRedisDurableJobStore(RedisDurableJobStore):
    """Redis store with pipelined candidate reads and job-local claim watches."""

    def __init__(self, redis_client, *, prefix: str = "maestro:durable", claim_window: int = 16) -> None:
        super().__init__(redis_client, prefix=prefix)
        if claim_window < 1:
            raise ValueError("claim_window must be positive")
        self._claim_window = claim_window

    async def _candidate_jobs(self, now: float) -> list[ExecutionJob]:
        candidate_ids = await self._redis.zrangebyscore(self._queue_key, "-inf", now)
        if not candidate_ids:
            return []

        async with self._redis.pipeline(transaction=False) as pipe:
            for job_id in candidate_ids:
                pipe.hgetall(self._job_key(job_id))
            raw_jobs = await pipe.execute()

        stale_ids: list[str] = []
        jobs: list[ExecutionJob] = []
        for job_id, raw in zip(candidate_ids, raw_jobs, strict=True):
            if not raw:
                stale_ids.append(job_id)
                continue
            job = self._job_from_hash(raw)
            if job.status not in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}:
                stale_ids.append(job_id)
                continue
            jobs.append(job)

        if stale_ids:
            await self._redis.zrem(self._queue_key, *stale_ids)
        return jobs

    @staticmethod
    def _worker_offset(worker_id: str, width: int) -> int:
        digest = hashlib.blake2b(worker_id.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % width

    async def claim(
        self,
        *,
        worker_id: str,
        lease_seconds: float,
        domains: Sequence[str] | None = None,
    ) -> ExecutionJob | None:
        if not worker_id.strip():
            raise ValueError("worker_id cannot be empty")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        allowed = set(domains) if domains is not None else None

        for retry_index in range(12):
            now = await self._now()
            candidates = []
            for job in await self._candidate_jobs(now):
                if job.cancel_requested:
                    continue
                if job.spec.deadline_at is not None and job.spec.deadline_at <= now:
                    await self._expire_queued_deadline(job.job_id, now)
                    continue
                if allowed is not None and job.spec.domain not in allowed:
                    continue
                candidates.append(job)

            if not candidates:
                return None

            candidates.sort(
                key=lambda job: (
                    int(job.spec.priority),
                    job.available_at,
                    job.created_at,
                    job.job_id,
                )
            )
            best_priority = int(candidates[0].spec.priority)
            priority_candidates = [
                job for job in candidates if int(job.spec.priority) == best_priority
            ][: self._claim_window]
            offset = (self._worker_offset(worker_id, len(priority_candidates)) + retry_index) % len(
                priority_candidates
            )
            selected = priority_candidates[offset]
            key = self._job_key(selected.job_id)

            async with self._redis.pipeline(transaction=True) as pipe:
                try:
                    # The job hash, not the shared queue ZSET, is the ownership
                    # authority. Watching the queue caused unrelated claims to
                    # invalidate each other under multi-worker load.
                    await pipe.watch(key)
                    current_data = await pipe.hgetall(key)
                    if not current_data:
                        await self._redis.zrem(self._queue_key, selected.job_id)
                        continue
                    current = self._job_from_hash(current_data)
                    if current.status not in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}:
                        continue
                    if current.available_at > now or current.cancel_requested:
                        continue
                    if current.spec.deadline_at is not None and current.spec.deadline_at <= now:
                        continue
                    if allowed is not None and current.spec.domain not in allowed:
                        continue

                    current.status = JobStatus.RUNNING
                    current.attempt += 1
                    current.worker_id = worker_id
                    current.lease_token = uuid.uuid4().hex
                    current.lease_expires_at = now + lease_seconds
                    current.updated_at = now

                    pipe.multi()
                    pipe.zrem(self._queue_key, current.job_id)
                    pipe.zadd(self._running_key, {current.job_id: current.lease_expires_at})
                    pipe.hset(key, mapping=self._job_mapping(current))
                    await pipe.execute()
                    return current
                except WatchError:
                    continue
        return None
