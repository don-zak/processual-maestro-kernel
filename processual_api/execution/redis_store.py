"""Redis-backed durable job store with cross-worker lease coordination.

This module is optional at import time: application startup does not construct
or require the store. A caller must explicitly pass an initialized Redis client.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from redis.exceptions import WatchError

from .durable import (
    DurableJobStore,
    ExecutionJob,
    ExecutionPriority,
    IdempotencyConflictError,
    JobLeaseLostError,
    JobNotFoundError,
    JobSpec,
    JobStatus,
    RetryPolicy,
    SubmitResult,
)

_TERMINAL = {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}


class RedisDurableJobStore(DurableJobStore):
    """Durable multi-worker store using Redis optimistic transactions.

    Redis server time is authoritative for leases and retry availability. Queue
    membership, job state, and lease expiry are persisted separately so a dead
    worker can be recovered without depending on its process memory.
    """

    def __init__(self, redis_client: Any, *, prefix: str = "maestro:durable") -> None:
        if not prefix.strip(":"):
            raise ValueError("prefix cannot be empty")
        self._redis = redis_client
        self._prefix = prefix.rstrip(":")

    @property
    def _queue_key(self) -> str:
        return f"{self._prefix}:queue"

    @property
    def _running_key(self) -> str:
        return f"{self._prefix}:running"

    def _job_key(self, job_id: str) -> str:
        return f"{self._prefix}:job:{job_id}"

    def _idem_key(self, key: str) -> str:
        return f"{self._prefix}:idem:{key}"

    async def _now(self) -> float:
        seconds, micros = await self._redis.time()
        return float(seconds) + float(micros) / 1_000_000

    @staticmethod
    def _spec_json(spec: JobSpec) -> str:
        return json.dumps(
            {
                "idempotency_key": spec.idempotency_key,
                "domain": spec.domain,
                "payload": dict(spec.payload),
                "priority": int(spec.priority),
                "retry": {
                    "max_attempts": spec.retry.max_attempts,
                    "initial_backoff_seconds": spec.retry.initial_backoff_seconds,
                    "max_backoff_seconds": spec.retry.max_backoff_seconds,
                },
                "deadline_at": spec.deadline_at,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _job_from_hash(data: Mapping[str, str]) -> ExecutionJob:
        if not data:
            raise JobNotFoundError("job not found")
        spec_data = json.loads(data["spec"])
        retry_data = spec_data["retry"]
        spec = JobSpec(
            idempotency_key=spec_data["idempotency_key"],
            domain=spec_data["domain"],
            payload=spec_data["payload"],
            priority=ExecutionPriority(int(spec_data["priority"])),
            retry=RetryPolicy(
                max_attempts=int(retry_data["max_attempts"]),
                initial_backoff_seconds=float(retry_data["initial_backoff_seconds"]),
                max_backoff_seconds=float(retry_data["max_backoff_seconds"]),
            ),
            deadline_at=(
                None if spec_data["deadline_at"] is None else float(spec_data["deadline_at"])
            ),
        )
        result_raw = data.get("result", "")
        return ExecutionJob(
            job_id=data["job_id"],
            spec=spec,
            status=JobStatus(data["status"]),
            created_at=float(data["created_at"]),
            updated_at=float(data["updated_at"]),
            available_at=float(data["available_at"]),
            attempt=int(data.get("attempt", "0")),
            worker_id=data.get("worker_id") or None,
            lease_token=data.get("lease_token") or None,
            lease_expires_at=(
                float(data["lease_expires_at"]) if data.get("lease_expires_at") else None
            ),
            cancel_requested=data.get("cancel_requested", "0") == "1",
            last_error=data.get("last_error") or None,
            result=json.loads(result_raw) if result_raw else None,
        )

    @staticmethod
    def _job_mapping(job: ExecutionJob) -> dict[str, str]:
        return {
            "job_id": job.job_id,
            "spec": RedisDurableJobStore._spec_json(job.spec),
            "status": job.status.value,
            "created_at": repr(job.created_at),
            "updated_at": repr(job.updated_at),
            "available_at": repr(job.available_at),
            "attempt": str(job.attempt),
            "worker_id": job.worker_id or "",
            "lease_token": job.lease_token or "",
            "lease_expires_at": "" if job.lease_expires_at is None else repr(job.lease_expires_at),
            "cancel_requested": "1" if job.cancel_requested else "0",
            "last_error": job.last_error or "",
            "result": "" if job.result is None else json.dumps(job.result, separators=(",", ":")),
        }

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
                    pipe.zadd(self._queue_key, {job.job_id: now})
                    await pipe.execute()
                    return SubmitResult(job=job, created=True)
                except WatchError:
                    continue
        raise RuntimeError("durable submit contention exceeded retry budget")

    async def get(self, job_id: str) -> ExecutionJob:
        data = await self._redis.hgetall(self._job_key(job_id))
        if not data:
            raise JobNotFoundError(job_id)
        return self._job_from_hash(data)

    async def _expire_queued_deadline(self, job_id: str, now: float) -> bool:
        key = self._job_key(job_id)
        for _ in range(8):
            async with self._redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(key, self._queue_key)
                    data = await pipe.hgetall(key)
                    if not data:
                        pipe.multi()
                        pipe.zrem(self._queue_key, job_id)
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
                    pipe.zrem(self._queue_key, job_id)
                    await pipe.execute()
                    return True
                except WatchError:
                    continue
        return False

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

        for _ in range(12):
            now = await self._now()
            candidate_ids = await self._redis.zrangebyscore(self._queue_key, "-inf", now)
            candidates: list[ExecutionJob] = []
            for job_id in candidate_ids:
                try:
                    job = await self.get(job_id)
                except JobNotFoundError:
                    await self._redis.zrem(self._queue_key, job_id)
                    continue
                if job.status not in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}:
                    await self._redis.zrem(self._queue_key, job_id)
                    continue
                if job.cancel_requested:
                    continue
                if job.spec.deadline_at is not None and job.spec.deadline_at <= now:
                    await self._expire_queued_deadline(job_id, now)
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
            selected = candidates[0]
            key = self._job_key(selected.job_id)
            async with self._redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(self._queue_key, key)
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
                    token = uuid.uuid4().hex
                    current.status = JobStatus.RUNNING
                    current.attempt += 1
                    current.worker_id = worker_id
                    current.lease_token = token
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
                    await pipe.watch(key, self._running_key)
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
                        if job.status in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}:
                            pipe.zadd(self._queue_key, {job_id: job.available_at})
                        else:
                            pipe.zrem(self._queue_key, job_id)
                    await pipe.execute()
                    return job
                except WatchError:
                    continue
        raise JobLeaseLostError(f"job lease changed during mutation: {job_id}")

    async def heartbeat(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        lease_seconds: float,
    ) -> ExecutionJob:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")

        def mutate(job: ExecutionJob, now: float) -> None:
            if job.spec.deadline_at is not None and job.spec.deadline_at <= now:
                job.status = JobStatus.FAILED
                job.last_error = "deadline_exceeded"
                job.updated_at = now
                job.worker_id = None
                job.lease_token = None
                job.lease_expires_at = None
                return
            job.lease_expires_at = now + lease_seconds
            job.updated_at = now

        updated = await self._mutate_claimed(
            job_id=job_id,
            worker_id=worker_id,
            lease_token=lease_token,
            mutate=mutate,
        )
        if updated.status is JobStatus.FAILED and updated.last_error == "deadline_exceeded":
            raise JobLeaseLostError(f"job deadline expired: {job_id}")
        return updated

    async def release_unstarted_claim(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        delay_seconds: float = 0.0,
    ) -> ExecutionJob:
        if delay_seconds < 0:
            raise ValueError("delay_seconds cannot be negative")

        def mutate(job: ExecutionJob, now: float) -> None:
            job.status = JobStatus.QUEUED
            job.attempt = max(job.attempt - 1, 0)
            job.available_at = now + delay_seconds
            job.updated_at = now
            job.worker_id = None
            job.lease_token = None
            job.lease_expires_at = None

        return await self._mutate_claimed(
            job_id=job_id,
            worker_id=worker_id,
            lease_token=lease_token,
            mutate=mutate,
        )

    async def succeed(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        result: Any = None,
    ) -> ExecutionJob:
        def mutate(job: ExecutionJob, now: float) -> None:
            if job.cancel_requested:
                job.status = JobStatus.CANCELLED
            elif job.spec.deadline_at is not None and job.spec.deadline_at <= now:
                job.status = JobStatus.FAILED
                job.last_error = "deadline_exceeded"
            else:
                job.status = JobStatus.SUCCEEDED
                job.result = result
                job.last_error = None
            job.updated_at = now
            job.worker_id = None
            job.lease_token = None
            job.lease_expires_at = None

        return await self._mutate_claimed(
            job_id=job_id,
            worker_id=worker_id,
            lease_token=lease_token,
            mutate=mutate,
        )

    async def fail(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        error: str,
    ) -> ExecutionJob:
        def mutate(job: ExecutionJob, now: float) -> None:
            job.last_error = error
            job.updated_at = now
            job.worker_id = None
            job.lease_token = None
            job.lease_expires_at = None
            if job.cancel_requested:
                job.status = JobStatus.CANCELLED
                return
            if job.spec.deadline_at is not None and job.spec.deadline_at <= now:
                job.status = JobStatus.FAILED
                job.last_error = "deadline_exceeded"
                return
            if job.attempt >= job.spec.retry.max_attempts:
                job.status = JobStatus.FAILED
                return
            retry_at = now + job.spec.retry.delay_after_attempt(job.attempt)
            if job.spec.deadline_at is not None and retry_at >= job.spec.deadline_at:
                job.status = JobStatus.FAILED
                job.last_error = "deadline_exceeded"
                return
            job.status = JobStatus.RETRY_WAIT
            job.available_at = retry_at

        return await self._mutate_claimed(
            job_id=job_id,
            worker_id=worker_id,
            lease_token=lease_token,
            mutate=mutate,
        )

    async def request_cancel(self, job_id: str) -> ExecutionJob:
        key = self._job_key(job_id)
        for _ in range(8):
            now = await self._now()
            async with self._redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(key, self._queue_key)
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
                        pipe.zrem(self._queue_key, job_id)
                    await pipe.execute()
                    return job
                except WatchError:
                    continue
        raise RuntimeError(f"cancel contention exceeded retry budget: {job_id}")

    async def cancel_claimed(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
    ) -> ExecutionJob:
        def mutate(job: ExecutionJob, now: float) -> None:
            job.status = JobStatus.CANCELLED
            job.cancel_requested = True
            job.updated_at = now
            job.worker_id = None
            job.lease_token = None
            job.lease_expires_at = None

        return await self._mutate_claimed(
            job_id=job_id,
            worker_id=worker_id,
            lease_token=lease_token,
            mutate=mutate,
        )

    async def recover_expired_leases(self) -> int:
        now = await self._now()
        expired_ids = await self._redis.zrangebyscore(self._running_key, "-inf", now)
        recovered = 0
        for job_id in expired_ids:
            key = self._job_key(job_id)
            for _ in range(8):
                async with self._redis.pipeline(transaction=True) as pipe:
                    try:
                        await pipe.watch(key, self._running_key)
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
                        if job.status is JobStatus.QUEUED:
                            pipe.zadd(self._queue_key, {job_id: now})
                        await pipe.execute()
                        recovered += 1
                        break
                    except WatchError:
                        continue
        return recovered
