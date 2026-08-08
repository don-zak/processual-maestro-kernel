import asyncio

import pytest

from processual_api.execution.adaptive import (
    AdaptiveConcurrencyController,
    AdaptiveConcurrencyGate,
    AdaptiveConcurrencyPolicy,
    AdaptiveConcurrencySample,
    AdaptiveFailureKind,
    AdaptiveTelemetrySampler,
)
from processual_api.execution.durable import (
    InMemoryDurableJobStore,
    JobSpec,
    JobStatus,
    RetryPolicy,
)
from processual_api.execution.pool import DurableWorkerPool, DurableWorkerPoolPolicy
from processual_api.execution.worker import DurableWorker


def adaptive_gate(*, initial_limit: int = 4) -> AdaptiveConcurrencyGate:
    return AdaptiveConcurrencyGate(
        AdaptiveConcurrencyController(
            AdaptiveConcurrencyPolicy(
                minimum=1,
                maximum=4,
                additive_step=1,
                decrease_ratio=0.5,
                latency_target_ms=100.0,
                error_rate_threshold=0.1,
                recovery_windows=2,
                pressure_windows=2,
                healthy_latency_ratio=0.9,
                ewma_alpha=1.0,
            ),
            initial_limit=initial_limit,
        )
    )


@pytest.mark.asyncio
async def test_gate_applies_rate_limit_pressure_then_recovers_gradually() -> None:
    gate = adaptive_gate(initial_limit=4)

    assert await gate.observe(
        AdaptiveConcurrencySample(
            requests=100,
            latency_p95_ms=60.0,
            rate_limited=1,
        )
    ) == 2

    healthy = AdaptiveConcurrencySample(requests=100, latency_p95_ms=60.0)
    assert await gate.observe(healthy) == 2
    assert await gate.observe(healthy) == 3
    assert await gate.observe(healthy) == 3
    assert await gate.observe(healthy) == 4


@pytest.mark.asyncio
async def test_gate_applies_slow_provider_pressure_with_hysteresis() -> None:
    gate = adaptive_gate(initial_limit=4)
    slow = AdaptiveConcurrencySample(requests=100, latency_p95_ms=180.0)

    assert await gate.observe(slow) == 4
    assert await gate.observe(slow) == 2


@pytest.mark.asyncio
async def test_gate_limit_decrease_does_not_cancel_active_work() -> None:
    gate = adaptive_gate(initial_limit=2)
    first_entered = asyncio.Event()
    second_entered = asyncio.Event()
    release = asyncio.Event()

    async def hold(marker: asyncio.Event) -> None:
        await gate.acquire()
        marker.set()
        try:
            await release.wait()
        finally:
            await gate.release()

    first = asyncio.create_task(hold(first_entered))
    second = asyncio.create_task(hold(second_entered))
    await asyncio.wait_for(first_entered.wait(), timeout=0.2)
    await asyncio.wait_for(second_entered.wait(), timeout=0.2)
    assert gate.active == 2

    assert await gate.observe(
        AdaptiveConcurrencySample(
            requests=10,
            latency_p95_ms=60.0,
            timeouts=1,
        )
    ) == 1
    assert gate.active == 2

    release.set()
    await asyncio.gather(first, second)
    assert gate.active == 0


@pytest.mark.asyncio
async def test_gate_limit_increase_wakes_waiting_worker_immediately() -> None:
    gate = adaptive_gate(initial_limit=1)
    first_acquired = asyncio.Event()
    second_acquired = asyncio.Event()
    release = asyncio.Event()

    async def first_holder() -> None:
        await gate.acquire()
        first_acquired.set()
        try:
            await release.wait()
        finally:
            await gate.release()

    async def second_holder() -> None:
        await gate.acquire()
        second_acquired.set()
        await gate.release()

    first = asyncio.create_task(first_holder())
    await asyncio.wait_for(first_acquired.wait(), timeout=0.2)
    second = asyncio.create_task(second_holder())
    await asyncio.sleep(0)
    assert second_acquired.is_set() is False

    healthy = AdaptiveConcurrencySample(requests=100, latency_p95_ms=60.0)
    assert await gate.observe(healthy) == 1
    assert await gate.observe(healthy) == 2
    await asyncio.wait_for(second_acquired.wait(), timeout=0.2)

    release.set()
    await asyncio.gather(first, second)


@pytest.mark.asyncio
async def test_worker_pool_respects_opt_in_adaptive_gate() -> None:
    store = InMemoryDurableJobStore()
    for index in range(4):
        await store.submit(
            JobSpec(idempotency_key=f"adaptive-{index}", domain="provider", payload={})
        )

    gate = adaptive_gate(initial_limit=1)
    release = asyncio.Event()
    first_started = asyncio.Event()
    active = 0
    peak_active = 0

    async def handler(job):
        nonlocal active, peak_active
        active += 1
        peak_active = max(peak_active, active)
        first_started.set()
        try:
            await release.wait()
            return job.job_id
        finally:
            active -= 1

    workers = [
        DurableWorker(
            store=store,
            worker_id=f"adaptive-{index}",
            handlers={"provider": handler},
        )
        for index in range(4)
    ]
    pool = DurableWorkerPool(
        store=store,
        workers=workers,
        adaptive_gate=gate,
        policy=DurableWorkerPoolPolicy(
            idle_poll_seconds=0.005,
            recovery_interval_seconds=0.02,
        ),
    )

    await pool.start()
    try:
        await asyncio.wait_for(first_started.wait(), timeout=0.2)
        await asyncio.sleep(0.02)
        assert peak_active == 1

        healthy = AdaptiveConcurrencySample(requests=100, latency_p95_ms=60.0)
        assert await gate.observe(healthy) == 1
        assert await gate.observe(healthy) == 2

        async with asyncio.timeout(0.2):
            while peak_active < 2:
                await asyncio.sleep(0)
        assert peak_active == 2
    finally:
        release.set()
        await pool.stop(graceful_timeout_seconds=0.5)

    jobs = [await store.get(job_id) for job_id in store._jobs]  # type: ignore[attr-defined]
    assert all(job.status in {JobStatus.SUCCEEDED, JobStatus.QUEUED} for job in jobs)


@pytest.mark.asyncio
async def test_pool_automatically_throttles_on_rate_limit_then_recovers() -> None:
    class RateLimitedError(RuntimeError):
        pass

    store = InMemoryDurableJobStore()
    gate = adaptive_gate(initial_limit=4)
    sampler = AdaptiveTelemetrySampler(
        window_size=1,
        failure_classifier=lambda job: (
            AdaptiveFailureKind.RATE_LIMITED
            if job.last_error == "RateLimitedError"
            else AdaptiveFailureKind.ERROR
        ),
    )

    async def handler(job):
        if job.spec.payload.get("rate_limited"):
            raise RateLimitedError("provider returned 429")
        return job.job_id

    worker = DurableWorker(
        store=store,
        worker_id="adaptive-feedback",
        handlers={"provider": handler},
    )
    pool = DurableWorkerPool(
        store=store,
        workers=[worker],
        adaptive_gate=gate,
        adaptive_sampler=sampler,
        policy=DurableWorkerPoolPolicy(
            idle_poll_seconds=0.005,
            recovery_interval_seconds=0.02,
        ),
    )

    limited = await store.submit(
        JobSpec(
            idempotency_key="provider-429",
            domain="provider",
            payload={"rate_limited": True},
            retry=RetryPolicy(max_attempts=1),
        )
    )
    await pool.start()
    try:
        async with asyncio.timeout(0.5):
            while gate.current_limit != 2:
                await asyncio.sleep(0)
        assert (await store.get(limited.job.job_id)).status is JobStatus.FAILED

        healthy_ids = []
        for index in range(4):
            submitted = await store.submit(
                JobSpec(
                    idempotency_key=f"provider-healthy-{index}",
                    domain="provider",
                    payload={},
                )
            )
            healthy_ids.append(submitted.job.job_id)

        async with asyncio.timeout(0.5):
            while gate.current_limit != 4:
                await asyncio.sleep(0)
        assert all(
            (await store.get(job_id)).status is JobStatus.SUCCEEDED
            for job_id in healthy_ids
        )
    finally:
        await pool.stop(graceful_timeout_seconds=0.5)


def test_pool_rejects_sampler_without_adaptive_gate() -> None:
    store = InMemoryDurableJobStore()

    async def handler(job):
        return job.job_id

    worker = DurableWorker(
        store=store,
        worker_id="adaptive-validation",
        handlers={"provider": handler},
    )
    with pytest.raises(ValueError, match="adaptive_sampler requires adaptive_gate"):
        DurableWorkerPool(
            store=store,
            workers=[worker],
            adaptive_sampler=AdaptiveTelemetrySampler(window_size=1),
        )
