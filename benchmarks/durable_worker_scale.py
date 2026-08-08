"""Synthetic qualification harness for durable worker scaling.

This module measures execution-platform behavior only. It does not change runtime
worker counts or production defaults and must not be used as a startup gate.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
import uuid
from dataclasses import asdict, dataclass

import redis.asyncio as redis

from processual_api.execution.durable import JobSpec, JobStatus
from processual_api.execution.pool import DurableWorkerPool, DurableWorkerPoolPolicy
from processual_api.execution.redis_store import RedisDurableJobStore
from processual_api.execution.worker import DurableWorker


@dataclass(frozen=True, slots=True)
class ScaleResult:
    workers: int
    jobs: int
    completed: int
    true_errors: int
    elapsed_seconds: float
    successful_workflows_per_second: float
    queue_delay_p50_ms: float
    queue_delay_p95_ms: float
    queue_delay_p99_ms: float
    execution_p95_ms: float


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(max(math.ceil(q * len(ordered)) - 1, 0), len(ordered) - 1)
    return ordered[index]


async def run_scale_scenario(
    *,
    redis_url: str,
    workers: int,
    jobs: int,
    handler_delay_seconds: float,
) -> ScaleResult:
    if workers < 1 or jobs < 1:
        raise ValueError("workers and jobs must be positive")
    if handler_delay_seconds < 0:
        raise ValueError("handler_delay_seconds cannot be negative")

    client = redis.from_url(redis_url, decode_responses=True)
    prefix = f"{{durable-scale-{uuid.uuid4().hex}}}"
    store = RedisDurableJobStore(client, prefix=prefix)
    started_at: dict[str, float] = {}
    finished_at: dict[str, float] = {}

    async def handler(job):
        started_at[job.job_id] = time.perf_counter()
        await asyncio.sleep(handler_delay_seconds)
        finished_at[job.job_id] = time.perf_counter()
        return {"ok": True}

    worker_instances = [
        DurableWorker(
            store=store,
            worker_id=f"scale-{index}",
            handlers={"qualification": handler},
            lease_seconds=max(handler_delay_seconds * 5, 1.0),
            heartbeat_interval_seconds=max(min(handler_delay_seconds, 0.1), 0.01),
        )
        for index in range(workers)
    ]
    pool = DurableWorkerPool(
        store=store,
        workers=worker_instances,
        policy=DurableWorkerPoolPolicy(
            idle_poll_seconds=0.002,
            recovery_interval_seconds=0.05,
        ),
    )

    submitted_at: dict[str, float] = {}
    for index in range(jobs):
        result = await store.submit(
            JobSpec(
                idempotency_key=f"scale-{workers}-{index}",
                domain="qualification",
                payload={"index": index},
            )
        )
        submitted_at[result.job.job_id] = time.perf_counter()

    wall_start = time.perf_counter()
    await pool.start()
    try:
        deadline = wall_start + max(10.0, jobs * max(handler_delay_seconds, 0.01) * 3)
        final_jobs = []
        while True:
            final_jobs = [await store.get(job_id) for job_id in submitted_at]
            if all(job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED} for job in final_jobs):
                break
            if time.perf_counter() >= deadline:
                raise TimeoutError("durable scale scenario did not finish")
            await asyncio.sleep(0.005)
    finally:
        await pool.stop(graceful_timeout_seconds=1.0)
        await client.aclose()

    elapsed = time.perf_counter() - wall_start
    completed = sum(job.status is JobStatus.SUCCEEDED for job in final_jobs)
    true_errors = sum(job.status is not JobStatus.SUCCEEDED for job in final_jobs)
    queue_delays = [
        (started_at[job_id] - submit_time) * 1000
        for job_id, submit_time in submitted_at.items()
        if job_id in started_at
    ]
    execution_times = [
        (finished_at[job_id] - started_at[job_id]) * 1000
        for job_id in finished_at
        if job_id in started_at
    ]

    return ScaleResult(
        workers=workers,
        jobs=jobs,
        completed=completed,
        true_errors=true_errors,
        elapsed_seconds=elapsed,
        successful_workflows_per_second=(completed / elapsed if elapsed else 0.0),
        queue_delay_p50_ms=statistics.median(queue_delays) if queue_delays else 0.0,
        queue_delay_p95_ms=percentile(queue_delays, 0.95),
        queue_delay_p99_ms=percentile(queue_delays, 0.99),
        execution_p95_ms=percentile(execution_times, 0.95),
    )


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6379/15")
    parser.add_argument("--workers", default="1,2,4")
    parser.add_argument("--jobs", type=int, default=48)
    parser.add_argument("--handler-delay-ms", type=float, default=20.0)
    args = parser.parse_args()

    results = []
    for workers in [int(value) for value in args.workers.split(",") if value.strip()]:
        results.append(
            await run_scale_scenario(
                redis_url=args.redis_url,
                workers=workers,
                jobs=args.jobs,
                handler_delay_seconds=args.handler_delay_ms / 1000,
            )
        )
    print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(_main())
