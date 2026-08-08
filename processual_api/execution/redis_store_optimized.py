"""Contention-reduced Redis durable store.

This implementation preserves RedisDurableJobStore semantics while optimizing
the claim path. It is opt-in until qualification proves it is safe to promote
as the default durable Redis store.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence

from redis.exceptions import WatchError

from .durable import (
    ExecutionJob,
    ExecutionPriority,
    IdempotencyConflictError,
    JobLeaseLostError,
    JobNotFoundError,
    JobSpec,
    JobStatus,
    SubmitResult,
)
from .redis_store import RedisDurableJobStore

_TERMINAL = {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}
_PRIORITY_ORDER = tuple(sorted(ExecutionPriority, key=int))

_ATOMIC_CLAIM_LUA = r"""
local now = tonumber(ARGV[1])
local worker_id = ARGV[2]
local lease_expires_at = tonumber(ARGV[3])
local lease_token = ARGV[4]
local job_prefix = ARGV[5]
local window = tonumber(ARGV[6])

for priority_index = 1, 4 do
  local ids = redis.call('ZRANGEBYSCORE', KEYS[priority_index], '-inf', now, 'LIMIT', 0, window)
  for _, job_id in ipairs(ids) do
    local job_key = job_prefix .. job_id
    local status = redis.call('HGET', job_key, 'status')
    if not status then
      redis.call('ZREM', KEYS[priority_index], job_id)
      redis.call('ZREM', KEYS[5], job_id)
    elseif status ~= 'queued' and status ~= 'retry_wait' then
      redis.call('ZREM', KEYS[priority_index], job_id)
      redis.call('ZREM', KEYS[5], job_id)
    else
      local cancel_requested = redis.call('HGET', job_key, 'cancel_requested')
      local available_at = tonumber(redis.call('HGET', job_key, 'available_at') or '0')
      local spec_raw = redis.call('HGET', job_key, 'spec')
      local deadline_at = nil
      if spec_raw then
        local spec = cjson.decode(spec_raw)
        deadline_at = spec['deadline_at']
      end

      if cancel_requested == '1' then
        redis.call('HSET', job_key,
          'status', 'cancelled',
          'updated_at', tostring(now),
          'worker_id', '',
          'lease_token', '',
          'lease_expires_at', '')
        redis.call('ZREM', KEYS[priority_index], job_id)
        redis.call('ZREM', KEYS[5], job_id)
      elseif deadline_at ~= nil and deadline_at ~= cjson.null and tonumber(deadline_at) <= now then
        redis.call('HSET', job_key,
          'status', 'failed',
          'last_error', 'deadline_exceeded',
          'updated_at', tostring(now),
          'worker_id', '',
          'lease_token', '',
          'lease_expires_at', '')
        redis.call('ZREM', KEYS[priority_index], job_id)
        redis.call('ZREM', KEYS[5], job_id)
      elseif available_at <= now then
        redis.call('HINCRBY', job_key, 'attempt', 1)
        redis.call('HSET', job_key,
          'status', 'running',
          'updated_at', tostring(now),
          'worker_id', worker_id,
          'lease_token', lease_token,
          'lease_expires_at', tostring(lease_expires_at))
        redis.call('ZREM', KEYS[priority_index], job_id)
        redis.call('ZREM', KEYS[5], job_id)
        redis.call('ZADD', KEYS[6], lease_expires_at, job_id)
        return job_id
      end
    end
  end
end
return false
"""


class OptimizedRedisDurableJobStore(RedisDurableJobStore):
    """Redis store with priority indexes and contention-reduced claims."""

    def __init__(
        self,
        redis_client,
        *,
        prefix: str = "maestro:durable",
        candidate_window: int = 16,
    ) -> None:
        super().__init__(redis_client, prefix=prefix)
        if candidate_window < 1:
            raise ValueError("candidate_window must be positive")
        self._candidate_window = candidate_window

    def _priority_queue_key(self, priority: ExecutionPriority) -> str:
        return f"{self._prefix}:queue:p{int(priority)}"

    def _queue_job(self, pipe, job: ExecutionJob) -> None:
        pipe.zadd(self._queue_key, {job.job_id: job.available_at})
        pipe.zadd(self._priority_queue_key(job.spec.priority), {job.job_id: job.available_at})

    def _dequeue_job(self, pipe, job: ExecutionJob) -> None:
        pipe.zrem(self._queue_key, job.job_id)
        pipe.zrem(self._priority_queue_key(job.spec.priority), job.job_id)

    def _supports_atomic_claim(self) -> bool:
        start = self._prefix.find("{")
        end = self._prefix.find("}", start + 1)
        return start >= 0 and end > start + 1

    async def submit(self, spec: JobSpec) -> SubmitResult:
        idem_key = self._idem_key(spec.idempotency_key)
        for _ in range(8):
            async with self._redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(idem_key)
                    existing_id = await pipe.get(idem_key)
                    if existing_id:
                        existing = await self.get(existing_id)
                        if existing.spec != spec:
                            raise IdempotencyConflictError(
                                f"idempotency key already belongs to another job: {spec.idempotency_key}"
                            )
                        return SubmitResult(job=existing, created=False)

                    now = await self._now()
                    job = ExecutionJob(
                        job_id=uuid.uuid4().hex,
                        spec=spec,
                        status=JobStatus.QUEUED,
                        created_at=now,
                        updated_at=now,
                        available_at=now,
                    )
                    pipe.multi()
                    pipe.hset(self._job_key(job.job_id), mapping=self._job_mapping(job))
                    pipe.set(idem_key, job.job_id)
                    self._queue_job(pipe, job)
                    await pipe.execute()
                    return SubmitResult(job=job, created=True)
                except WatchError:
                    continue
        raise RuntimeError("durable submit contention exceeded retry budget")

    async def _candidate_ids(
        self,
        *,
        priority: ExecutionPriority,
        now: float,
        bounded: bool,
    ) -> list[str]:
        kwargs = {"start": 0, "num": self._candidate_window} if bounded else {}
        return await self._redis.zrangebyscore(
            self._priority_queue_key(priority),
            "-inf",
            now,
            **kwargs,
        )

    async def _hydrate_candidates(self, job_ids: list[str]) -> list[ExecutionJob]:
        if not job_ids:
            return []
        async with self._redis.pipeline(transaction=False) as pipe:
            for job_id in job_ids:
                pipe.hgetall(self._job_key(job_id))
            raw_jobs = await pipe.execute()

        jobs: list[ExecutionJob] = []
        stale_ids: list[str] = []
        for job_id, raw in zip(job_ids, raw_jobs, strict=True):
            if not raw:
                stale_ids.append(job_id)
                continue
            job = self._job_from_hash(raw)
            if job.status not in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}:
                stale_ids.append(job_id)
                continue
            jobs.append(job)

        if stale_ids:
            async with self._redis.pipeline(transaction=False) as pipe:
                pipe.zrem(self._queue_key, *stale_ids)
                for priority in _PRIORITY_ORDER:
                    pipe.zrem(self._priority_queue_key(priority), *stale_ids)
                await pipe.execute()
        return jobs

    async def _expire_queued_deadline(self, job_id: str, now: float) -> bool:
        key = self._job_key(job_id)
        for _ in range(8):
            async with self._redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(key)
                    data = await pipe.hgetall(key)
                    if not data:
                        pipe.multi()
                        pipe.zrem(self._queue_key, job_id)
                        for priority in _PRIORITY_ORDER:
                            pipe.zrem(self._priority_queue_key(priority), job_id)
                        await pipe.execute()
                        return False
                    job = self._job_from_hash(data)
                    if job.status not in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}:
                        return False
                    if job.spec.deadline_at is None or job.spec.deadline_at > now:
                        return False
                    job.status = JobStatus.FAILED
                    job.last_error = "deadline_exceeded"
                    job.updated_at = now
                    job.worker_id = None
                    job.lease_token = None
                    job.lease_expires_at = None
                    pipe.multi()
                    pipe.hset(key, mapping=self._job_mapping(job))
                    self._dequeue_job(pipe, job)
                    await pipe.execute()
                    return True
                except WatchError:
                    continue
        return False

    async def _claim_atomic(self, *, worker_id: str, lease_seconds: float) -> ExecutionJob | None:
        now = await self._now()
        lease_token = uuid.uuid4().hex
        lease_expires_at = now + lease_seconds
        job_id = await self._redis.eval(
            _ATOMIC_CLAIM_LUA,
            6,
            *(self._priority_queue_key(priority) for priority in _PRIORITY_ORDER),
            self._queue_key,
            self._running_key,
            now,
            worker_id,
            lease_expires_at,
            lease_token,
            f"{self._prefix}:job:",
            self._candidate_window,
        )
        if not job_id:
            return None
        return await self.get(job_id)

    async def _claim_watch(
        self,
        *,
        worker_id: str,
        lease_seconds: float,
        domains: Sequence[str] | None,
    ) -> ExecutionJob | None:
        allowed = set(domains) if domains is not None else None
        for _ in range(12):
            now = await self._now()
            selected: ExecutionJob | None = None
            for priority in _PRIORITY_ORDER:
                candidate_ids = await self._candidate_ids(
                    priority=priority,
                    now=now,
                    bounded=allowed is None,
                )
                candidates = await self._hydrate_candidates(candidate_ids)
                candidates.sort(key=lambda job: (job.available_at, job.created_at, job.job_id))
                for job in candidates:
                    if job.cancel_requested:
                        continue
                    if job.spec.priority is not priority:
                        continue
                    if job.spec.deadline_at is not None and job.spec.deadline_at <= now:
                        await self._expire_queued_deadline(job.job_id, now)
                        continue
                    if allowed is not None and job.spec.domain not in allowed:
                        continue
                    selected = job
                    break
                if selected is not None:
                    break

            if selected is None:
                return None

            key = self._job_key(selected.job_id)
            async with self._redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(key)
                    current_data = await pipe.hgetall(key)
                    if not current_data:
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
                    self._dequeue_job(pipe, current)
                    pipe.zadd(self._running_key, {current.job_id: current.lease_expires_at})
                    pipe.hset(key, mapping=self._job_mapping(current))
                    await pipe.execute()
                    return current
                except WatchError:
                    continue
        return None

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
        if domains is None and self._supports_atomic_claim():
            return await self._claim_atomic(worker_id=worker_id, lease_seconds=lease_seconds)
        return await self._claim_watch(
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            domains=domains,
        )

    async def _mutate_claimed(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        mutate: Callable[[ExecutionJob, float], None],
    ) -> ExecutionJob:
        key = self._job_key(job_id)
        for _ in range(8):
            now = await self._now()
            async with self._redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(key)
                    data = await pipe.hgetall(key)
                    if not data:
                        raise JobNotFoundError(job_id)
                    job = self._job_from_hash(data)
                    if (
                        job.status is not JobStatus.RUNNING
                        or job.worker_id != worker_id
                        or job.lease_token != lease_token
                        or job.lease_expires_at is None
                        or job.lease_expires_at <= now
                    ):
                        raise JobLeaseLostError(f"job lease is not active: {job_id}")
                    mutate(job, now)
                    pipe.multi()
                    pipe.hset(key, mapping=self._job_mapping(job))
                    if job.status is JobStatus.RUNNING:
                        if job.lease_expires_at is None:
                            raise JobLeaseLostError(f"running job has no lease expiry: {job_id}")
                        pipe.zadd(self._running_key, {job_id: job.lease_expires_at})
                    else:
                        pipe.zrem(self._running_key, job_id)
                        self._dequeue_job(pipe, job)
                        if job.status in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}:
                            self._queue_job(pipe, job)
                    await pipe.execute()
                    return job
                except WatchError:
                    continue
        raise JobLeaseLostError(f"job lease changed during mutation: {job_id}")

    async def request_cancel(self, job_id: str) -> ExecutionJob:
        key = self._job_key(job_id)
        for _ in range(8):
            now = await self._now()
            async with self._redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(key)
                    data = await pipe.hgetall(key)
                    if not data:
                        raise JobNotFoundError(job_id)
                    job = self._job_from_hash(data)
                    if job.status in _TERMINAL:
                        return job
                    job.cancel_requested = True
                    job.updated_at = now
                    if job.status in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}:
                        job.status = JobStatus.CANCELLED
                    pipe.multi()
                    pipe.hset(key, mapping=self._job_mapping(job))
                    if job.status is JobStatus.CANCELLED:
                        self._dequeue_job(pipe, job)
                    await pipe.execute()
                    return job
                except WatchError:
                    continue
        raise RuntimeError(f"cancel contention exceeded retry budget: {job_id}")

    async def recover_expired_leases(self) -> int:
        now = await self._now()
        expired_ids = await self._redis.zrangebyscore(self._running_key, "-inf", now)
        recovered = 0
        for job_id in expired_ids:
            key = self._job_key(job_id)
            for _ in range(8):
                async with self._redis.pipeline(transaction=True) as pipe:
                    try:
                        await pipe.watch(key)
                        data = await pipe.hgetall(key)
                        if not data:
                            pipe.multi()
                            pipe.zrem(self._running_key, job_id)
                            await pipe.execute()
                            break
                        job = self._job_from_hash(data)
                        if (
                            job.status is not JobStatus.RUNNING
                            or job.lease_expires_at is None
                            or job.lease_expires_at > now
                        ):
                            break
                        job.worker_id = None
                        job.lease_token = None
                        job.lease_expires_at = None
                        job.updated_at = now
                        job.last_error = "worker_lease_expired"
                        if job.cancel_requested:
                            job.status = JobStatus.CANCELLED
                        elif job.spec.deadline_at is not None and job.spec.deadline_at <= now:
                            job.status = JobStatus.FAILED
                            job.last_error = "deadline_exceeded"
                        elif job.attempt >= job.spec.retry.max_attempts:
                            job.status = JobStatus.FAILED
                        else:
                            job.status = JobStatus.QUEUED
                            job.available_at = now
                        pipe.multi()
                        pipe.hset(key, mapping=self._job_mapping(job))
                        pipe.zrem(self._running_key, job_id)
                        self._dequeue_job(pipe, job)
                        if job.status is JobStatus.QUEUED:
                            self._queue_job(pipe, job)
                        await pipe.execute()
                        recovered += 1
                        break
                    except WatchError:
                        continue
        return recovered