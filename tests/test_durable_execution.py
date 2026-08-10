import pytest

from processual_api.execution.durable import (
    ExecutionPriority,
    IdempotencyConflictError,
    InMemoryDurableJobStore,
    JobLeaseLostError,
    JobSpec,
    JobStatus,
    RetryPolicy,
)


class FakeClock:
    def __init__(self, value: float = 1000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def spec(
    key: str,
    *,
    domain: str = "oss",
    priority: ExecutionPriority = ExecutionPriority.NORMAL,
    retry: RetryPolicy | None = None,
    deadline_at: float | None = None,
) -> JobSpec:
    return JobSpec(
        idempotency_key=key,
        domain=domain,
        payload={"key": key},
        priority=priority,
        retry=retry or RetryPolicy(),
        deadline_at=deadline_at,
    )


@pytest.mark.asyncio
async def test_submit_is_idempotent_for_identical_job() -> None:
    store = InMemoryDurableJobStore()
    job_spec = spec("same-request")

    first = await store.submit(job_spec)
    second = await store.submit(job_spec)

    assert first.created is True
    assert second.created is False
    assert second.job.job_id == first.job.job_id
    assert second.job.status is JobStatus.QUEUED


@pytest.mark.asyncio
async def test_submit_rejects_idempotency_key_reuse_for_different_job() -> None:
    store = InMemoryDurableJobStore()
    await store.submit(spec("duplicate", domain="oss"))

    with pytest.raises(IdempotencyConflictError):
        await store.submit(spec("duplicate", domain="billing"))


@pytest.mark.asyncio
async def test_claim_prefers_priority_and_can_filter_domains() -> None:
    store = InMemoryDurableJobStore()
    await store.submit(spec("batch", domain="billing", priority=ExecutionPriority.BATCH))
    await store.submit(spec("normal", domain="oss", priority=ExecutionPriority.NORMAL))
    await store.submit(spec("emergency", domain="noc", priority=ExecutionPriority.EMERGENCY))

    oss_job = await store.claim(worker_id="oss-worker", lease_seconds=30, domains=["oss"])
    assert oss_job is not None
    assert oss_job.spec.idempotency_key == "normal"

    emergency = await store.claim(worker_id="shared-worker", lease_seconds=30)
    assert emergency is not None
    assert emergency.spec.idempotency_key == "emergency"


@pytest.mark.asyncio
async def test_heartbeat_extends_active_lease_and_wrong_worker_is_rejected() -> None:
    clock = FakeClock()
    store = InMemoryDurableJobStore(clock=clock)
    submitted = await store.submit(spec("heartbeat"))
    claimed = await store.claim(worker_id="worker-a", lease_seconds=10)
    assert claimed is not None
    assert claimed.job_id == submitted.job.job_id
    original_expiry = claimed.lease_expires_at
    assert original_expiry is not None

    clock.advance(5)
    renewed = await store.heartbeat(
        job_id=claimed.job_id,
        worker_id="worker-a",
        lease_token=claimed.lease_token or "",
        lease_seconds=20,
    )
    assert renewed.lease_expires_at == clock.value + 20
    assert renewed.lease_expires_at > original_expiry

    with pytest.raises(JobLeaseLostError):
        await store.succeed(
            job_id=claimed.job_id,
            worker_id="worker-b",
            lease_token=claimed.lease_token or "",
        )


@pytest.mark.asyncio
async def test_success_requires_lease_and_persists_result() -> None:
    store = InMemoryDurableJobStore()
    await store.submit(spec("success"))
    claimed = await store.claim(worker_id="worker", lease_seconds=30)
    assert claimed is not None

    completed = await store.succeed(
        job_id=claimed.job_id,
        worker_id="worker",
        lease_token=claimed.lease_token or "",
        result={"ticket": "INC-42"},
    )

    assert completed.status is JobStatus.SUCCEEDED
    assert completed.result == {"ticket": "INC-42"}
    assert completed.worker_id is None
    assert completed.lease_token is None


@pytest.mark.asyncio
async def test_failure_uses_exponential_backoff_then_exhausts_attempts() -> None:
    clock = FakeClock()
    store = InMemoryDurableJobStore(clock=clock)
    retry = RetryPolicy(max_attempts=3, initial_backoff_seconds=2, max_backoff_seconds=10)
    await store.submit(spec("retry", retry=retry))

    first = await store.claim(worker_id="worker", lease_seconds=30)
    assert first is not None
    failed = await store.fail(
        job_id=first.job_id,
        worker_id="worker",
        lease_token=first.lease_token or "",
        error="provider_timeout",
    )
    assert failed.status is JobStatus.RETRY_WAIT
    assert failed.available_at == clock.value + 2
    assert await store.claim(worker_id="worker", lease_seconds=30) is None

    clock.advance(2)
    second = await store.claim(worker_id="worker", lease_seconds=30)
    assert second is not None
    failed = await store.fail(
        job_id=second.job_id,
        worker_id="worker",
        lease_token=second.lease_token or "",
        error="provider_timeout",
    )
    assert failed.status is JobStatus.RETRY_WAIT
    assert failed.available_at == clock.value + 4

    clock.advance(4)
    third = await store.claim(worker_id="worker", lease_seconds=30)
    assert third is not None
    failed = await store.fail(
        job_id=third.job_id,
        worker_id="worker",
        lease_token=third.lease_token or "",
        error="provider_timeout",
    )
    assert failed.status is JobStatus.FAILED
    assert failed.attempt == 3


@pytest.mark.asyncio
async def test_expired_worker_lease_is_recovered_and_reclaimable() -> None:
    clock = FakeClock()
    store = InMemoryDurableJobStore(clock=clock)
    await store.submit(spec("recover"))
    first = await store.claim(worker_id="dead-worker", lease_seconds=5)
    assert first is not None

    clock.advance(6)
    assert await store.recover_expired_leases() == 1

    recovered = await store.get(first.job_id)
    assert recovered.status is JobStatus.QUEUED
    assert recovered.last_error == "worker_lease_expired"
    assert recovered.worker_id is None

    second = await store.claim(worker_id="replacement", lease_seconds=5)
    assert second is not None
    assert second.job_id == first.job_id
    assert second.attempt == 2


@pytest.mark.asyncio
async def test_queued_cancellation_is_terminal_and_never_claimed() -> None:
    store = InMemoryDurableJobStore()
    submitted = await store.submit(spec("cancel-before-run"))

    cancelled = await store.request_cancel(submitted.job.job_id)

    assert cancelled.status is JobStatus.CANCELLED
    assert cancelled.cancel_requested is True
    assert await store.claim(worker_id="worker", lease_seconds=30) is None


@pytest.mark.asyncio
async def test_running_cancellation_is_cooperative_and_blocks_success() -> None:
    store = InMemoryDurableJobStore()
    await store.submit(spec("cancel-running"))
    claimed = await store.claim(worker_id="worker", lease_seconds=30)
    assert claimed is not None

    requested = await store.request_cancel(claimed.job_id)
    assert requested.status is JobStatus.RUNNING
    assert requested.cancel_requested is True

    completed = await store.succeed(
        job_id=claimed.job_id,
        worker_id="worker",
        lease_token=claimed.lease_token or "",
        result="must-not-commit",
    )
    assert completed.status is JobStatus.CANCELLED
    assert completed.result is None


@pytest.mark.asyncio
async def test_deadline_prevents_claim_and_retry_beyond_deadline() -> None:
    clock = FakeClock()
    store = InMemoryDurableJobStore(clock=clock)
    retry = RetryPolicy(max_attempts=3, initial_backoff_seconds=10, max_backoff_seconds=10)
    await store.submit(spec("deadline-retry", retry=retry, deadline_at=clock.value + 5))

    claimed = await store.claim(worker_id="worker", lease_seconds=30)
    assert claimed is not None
    failed = await store.fail(
        job_id=claimed.job_id,
        worker_id="worker",
        lease_token=claimed.lease_token or "",
        error="temporary",
    )
    assert failed.status is JobStatus.FAILED
    assert failed.last_error == "deadline_exceeded"

    await store.submit(spec("already-expired", deadline_at=clock.value))
    assert await store.claim(worker_id="worker", lease_seconds=30) is None
