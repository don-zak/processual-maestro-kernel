"""Durable execution contracts for long-running and distributed workflows.

The in-memory store is deliberately dependency-free. It defines the state and
lease semantics that persistent queue backends must preserve without putting a
new datastore dependency on application startup.
"""

from __future__ import annotations

import asyncio
import copy
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any, Protocol


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionPriority(IntEnum):
    """Lower values are claimed first; emergency capacity outranks batch work."""

    EMERGENCY = 0
    INTERACTIVE = 10
    NORMAL = 20
    BATCH = 30


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_backoff_seconds < 0:
            raise ValueError("initial_backoff_seconds cannot be negative")
        if self.max_backoff_seconds < self.initial_backoff_seconds:
            raise ValueError("max_backoff_seconds cannot be smaller than initial_backoff_seconds")

    def delay_after_attempt(self, attempt: int) -> float:
        if attempt < 1:
            raise ValueError("attempt must be at least 1")
        delay = self.initial_backoff_seconds * (2 ** (attempt - 1))
        return min(delay, self.max_backoff_seconds)


@dataclass(frozen=True, slots=True)
class JobSpec:
    idempotency_key: str
    domain: str
    payload: Mapping[str, Any]
    priority: ExecutionPriority = ExecutionPriority.NORMAL
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    deadline_at: float | None = None

    def __post_init__(self) -> None:
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key cannot be empty")
        if not self.domain.strip():
            raise ValueError("domain cannot be empty")


@dataclass(slots=True)
class ExecutionJob:
    job_id: str
    spec: JobSpec
    status: JobStatus
    created_at: float
    updated_at: float
    available_at: float
    attempt: int = 0
    worker_id: str | None = None
    lease_token: str | None = None
    lease_expires_at: float | None = None
    cancel_requested: bool = False
    last_error: str | None = None
    result: Any = None


@dataclass(frozen=True, slots=True)
class SubmitResult:
    job: ExecutionJob
    created: bool


class IdempotencyConflictError(RuntimeError):
    """Raised when one idempotency key is reused for a different job."""


class JobLeaseLostError(RuntimeError):
    """Raised when a worker tries to mutate a job without its active lease."""


class JobNotFoundError(LookupError):
    """Raised when a durable job identifier does not exist."""


class DurableJobStore(Protocol):
    async def submit(self, spec: JobSpec) -> SubmitResult: ...

    async def get(self, job_id: str) -> ExecutionJob: ...

    async def claim(
        self,
        *,
        worker_id: str,
        lease_seconds: float,
        domains: Sequence[str] | None = None,
    ) -> ExecutionJob | None: ...

    async def heartbeat(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        lease_seconds: float,
    ) -> ExecutionJob: ...

    async def succeed(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        result: Any = None,
    ) -> ExecutionJob: ...

    async def fail(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        error: str,
    ) -> ExecutionJob: ...

    async def request_cancel(self, job_id: str) -> ExecutionJob: ...

    async def cancel_claimed(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
    ) -> ExecutionJob: ...

    async def recover_expired_leases(self) -> int: ...


class InMemoryDurableJobStore:
    """Reference implementation of the durable execution state machine.

    It is suitable for tests and single-process development only. Production
    backends must provide the same atomic transition and lease semantics using
    shared durable storage.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._lock = asyncio.Lock()
        self._jobs: dict[str, ExecutionJob] = {}
        self._idempotency: dict[str, str] = {}

    @staticmethod
    def _clone(job: ExecutionJob) -> ExecutionJob:
        return copy.deepcopy(job)

    @staticmethod
    def _same_submission(existing: JobSpec, submitted: JobSpec) -> bool:
        return existing == submitted

    def _get(self, job_id: str) -> ExecutionJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise JobNotFoundError(job_id) from exc

    @staticmethod
    def _clear_lease(job: ExecutionJob) -> None:
        job.worker_id = None
        job.lease_token = None
        job.lease_expires_at = None

    def _assert_lease(
        self,
        job: ExecutionJob,
        *,
        worker_id: str,
        lease_token: str,
        now: float,
    ) -> None:
        if (
            job.status is not JobStatus.RUNNING
            or job.worker_id != worker_id
            or job.lease_token != lease_token
            or job.lease_expires_at is None
            or job.lease_expires_at <= now
        ):
            raise JobLeaseLostError(f"job lease is not active: {job.job_id}")

    def _deadline_expired(self, job: ExecutionJob, now: float) -> bool:
        return job.spec.deadline_at is not None and job.spec.deadline_at <= now

    def _expire_deadline(self, job: ExecutionJob, now: float) -> bool:
        if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}:
            return False
        if not self._deadline_expired(job, now):
            return False
        job.status = JobStatus.FAILED
        job.last_error = "deadline_exceeded"
        job.updated_at = now
        self._clear_lease(job)
        return True

    async def submit(self, spec: JobSpec) -> SubmitResult:
        async with self._lock:
            existing_id = self._idempotency.get(spec.idempotency_key)
            if existing_id is not None:
                existing = self._jobs[existing_id]
                if not self._same_submission(existing.spec, spec):
                    raise IdempotencyConflictError(
                        f"idempotency key already belongs to another job: {spec.idempotency_key}"
                    )
                return SubmitResult(job=self._clone(existing), created=False)

            now = self._clock()
            job = ExecutionJob(
                job_id=uuid.uuid4().hex,
                spec=spec,
                status=JobStatus.QUEUED,
                created_at=now,
                updated_at=now,
                available_at=now,
            )
            self._jobs[job.job_id] = job
            self._idempotency[spec.idempotency_key] = job.job_id
            return SubmitResult(job=self._clone(job), created=True)

    async def get(self, job_id: str) -> ExecutionJob:
        async with self._lock:
            return self._clone(self._get(job_id))

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

        allowed_domains = set(domains) if domains is not None else None
        async with self._lock:
            now = self._clock()
            for job in self._jobs.values():
                self._expire_deadline(job, now)

            candidates = [
                job
                for job in self._jobs.values()
                if job.status in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}
                and job.available_at <= now
                and not job.cancel_requested
                and (allowed_domains is None or job.spec.domain in allowed_domains)
            ]
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
            job = candidates[0]
            job.status = JobStatus.RUNNING
            job.attempt += 1
            job.worker_id = worker_id
            job.lease_token = uuid.uuid4().hex
            job.lease_expires_at = now + lease_seconds
            job.updated_at = now
            return self._clone(job)

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
        async with self._lock:
            now = self._clock()
            job = self._get(job_id)
            self._assert_lease(job, worker_id=worker_id, lease_token=lease_token, now=now)
            if self._deadline_expired(job, now):
                self._expire_deadline(job, now)
                raise JobLeaseLostError(f"job deadline expired: {job_id}")
            job.lease_expires_at = now + lease_seconds
            job.updated_at = now
            return self._clone(job)

    async def succeed(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        result: Any = None,
    ) -> ExecutionJob:
        async with self._lock:
            now = self._clock()
            job = self._get(job_id)
            self._assert_lease(job, worker_id=worker_id, lease_token=lease_token, now=now)
            if job.cancel_requested:
                job.status = JobStatus.CANCELLED
                job.updated_at = now
                self._clear_lease(job)
                return self._clone(job)
            if self._deadline_expired(job, now):
                self._expire_deadline(job, now)
                return self._clone(job)
            job.status = JobStatus.SUCCEEDED
            job.result = result
            job.last_error = None
            job.updated_at = now
            self._clear_lease(job)
            return self._clone(job)

    async def fail(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        error: str,
    ) -> ExecutionJob:
        async with self._lock:
            now = self._clock()
            job = self._get(job_id)
            self._assert_lease(job, worker_id=worker_id, lease_token=lease_token, now=now)
            job.last_error = error
            job.updated_at = now
            self._clear_lease(job)

            if job.cancel_requested:
                job.status = JobStatus.CANCELLED
                return self._clone(job)
            if self._deadline_expired(job, now):
                job.status = JobStatus.FAILED
                job.last_error = "deadline_exceeded"
                return self._clone(job)
            if job.attempt >= job.spec.retry.max_attempts:
                job.status = JobStatus.FAILED
                return self._clone(job)

            delay = job.spec.retry.delay_after_attempt(job.attempt)
            retry_at = now + delay
            if job.spec.deadline_at is not None and retry_at >= job.spec.deadline_at:
                job.status = JobStatus.FAILED
                job.last_error = "deadline_exceeded"
                return self._clone(job)
            job.status = JobStatus.RETRY_WAIT
            job.available_at = retry_at
            return self._clone(job)

    async def request_cancel(self, job_id: str) -> ExecutionJob:
        async with self._lock:
            now = self._clock()
            job = self._get(job_id)
            if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}:
                return self._clone(job)
            job.cancel_requested = True
            job.updated_at = now
            if job.status in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}:
                job.status = JobStatus.CANCELLED
            return self._clone(job)

    async def cancel_claimed(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
    ) -> ExecutionJob:
        async with self._lock:
            now = self._clock()
            job = self._get(job_id)
            self._assert_lease(job, worker_id=worker_id, lease_token=lease_token, now=now)
            job.status = JobStatus.CANCELLED
            job.cancel_requested = True
            job.updated_at = now
            self._clear_lease(job)
            return self._clone(job)

    async def recover_expired_leases(self) -> int:
        async with self._lock:
            now = self._clock()
            recovered = 0
            for job in self._jobs.values():
                if job.status is not JobStatus.RUNNING:
                    continue
                if job.lease_expires_at is None or job.lease_expires_at > now:
                    continue
                recovered += 1
                self._clear_lease(job)
                job.updated_at = now
                job.last_error = "worker_lease_expired"
                if job.cancel_requested:
                    job.status = JobStatus.CANCELLED
                elif self._deadline_expired(job, now):
                    job.status = JobStatus.FAILED
                    job.last_error = "deadline_exceeded"
                elif job.attempt >= job.spec.retry.max_attempts:
                    job.status = JobStatus.FAILED
                else:
                    job.status = JobStatus.QUEUED
                    job.available_at = now
            return recovered
