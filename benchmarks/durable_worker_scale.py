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
from processual_api.execution.redis_store_optimized import OptimizedRedisDurableJobStore
from processual_api.execution.worker import DurableWorker

_TELEMETRY_COMMANDS = (
    "eval",
    "hgetall",
    "time",
    "zrangebyscore",
    "zadd",
    "zrem",
    "watch",
    "multi",
    "exec",
)


@dataclass(frozen=True, slots=True)
class RedisTelemetrySnapshot:
    total_commands_processed: int
    used_cpu_sys: float
    used_cpu_user: float
    used_memory: int
    command_calls: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class RedisTelemetryDelta:
    total_commands_processed: int
    used_cpu_sys: float
    used_cpu_user: float
    used_memory_delta: int
    commands_per_completed_workflow: float
    command_calls: tuple[tuple[str, int], ...]


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
    redis_telemetry: RedisTelemetryDelta | None = None


@dataclass(frozen=True, slots=True)
class ScaleSummary:
    workers: int
    jobs: int
    repetitions: int
    completed_min: int
    true_errors_total: int
    successful_workflows_per_second_median: float
    queue_delay_p95_ms_median: float
    queue_delay_p99_ms_median: float
    execution_p95_ms_median: float
    trials: tuple[ScaleResult, ...]


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(max(math.ceil(q * len(ordered)) - 1, 0), len(ordered) - 1)
    return ordered[index]


def summarize_trials(trials: list[ScaleResult]) -> ScaleSummary:
    if not trials:
        raise ValueError("at least one scale trial is required")
    workers = trials[0].workers
    jobs = trials[0].jobs
    if any(trial.workers != workers or trial.jobs != jobs for trial in trials):
        raise ValueError("scale trials must use the same worker and job counts")
    return ScaleSummary(
        workers=workers,
        jobs=jobs,
        repetitions=len(trials),
        completed_min=min(trial.completed for trial in trials),
        true_errors_total=sum(trial.true_errors for trial in trials),
        successful_workflows_per_second_median=statistics.median(
            trial.successful_workflows_per_second for trial in trials
        ),
        queue_delay_p95_ms_median=statistics.median(trial.queue_delay_p95_ms for trial in trials),
        queue_delay_p99_ms_median=statistics.median(trial.queue_delay_p99_ms for trial in trials),
        execution_p95_ms_median=statistics.median(trial.execution_p95_ms for trial in trials),
        trials=tuple(trials),
    )


def _command_calls(commandstats: dict[str, object], command: str) -> int:
    entry = commandstats.get(f"cmdstat_{command}")
    if not isinstance(entry, dict):
        return 0
    calls = entry.get("calls", 0)
    return int(calls) if isinstance(calls, int | float | str) else 0


async def read_redis_telemetry(client) -> RedisTelemetrySnapshot:
    stats = await client.info("stats")
    cpu = await client.info("cpu")
    memory = await client.info("memory")
    commandstats = await client.info("commandstats")
    return RedisTelemetrySnapshot(
        total_commands_processed=int(stats.get("total_commands_processed", 0)),
        used_cpu_sys=float(cpu.get("used_cpu_sys", 0.0)),
        used_cpu_user=float(cpu.get("used_cpu_user", 0.0)),
        used_memory=int(memory.get("used_memory", 0)),
        command_calls=tuple(
            (command, _command_calls(commandstats, command)) for command in _TELEMETRY_COMMANDS
        ),
    )


def diff_redis_telemetry(
    before: RedisTelemetrySnapshot,
    after: RedisTelemetrySnapshot,
    *,
    completed: int,
) -> RedisTelemetryDelta:
    before_commands = dict(before.command_calls)
    after_commands = dict(after.command_calls)
    total_commands = max(after.total_commands_processed - before.total_commands_processed, 0)
    return RedisTelemetryDelta(
        total_commands_processed=total_commands,
        used_cpu_sys=max(after.used_cpu_sys - before.used_cpu_sys, 0.0),
        used_cpu_user=max(after.used_cpu_user - before.used_cpu_user, 0.0),
        used_memory_delta=after.used_memory - before.used_memory,
        commands_per_completed_workflow=(total_commands / completed if completed else 0.0),
        command_calls=tuple(
            (
                command,
                max(after_commands.get(command, 0) - before_commands.get(command, 0), 0),
            )
            for command in _TELEMETRY_COMMANDS
        ),
    )


async def run_scale_scenario(
    *,
    redis_url: str,
    workers: int,
    jobs: int,
    handler_delay_seconds: float,
    redis_telemetry: bool = False,
) -> ScaleResult:
    if workers < 1 or jobs < 1:
        raise ValueError("workers and jobs must be positive")
    if handler_delay_seconds < 0:
        raise ValueError("handler_delay_seconds cannot be negative")

    client = redis.from_url(redis_url, decode_responses=True)
    prefix = f"{{durable-scale-{uuid.uuid4().hex}}}"
    store = OptimizedRedisDurableJobStore(client, prefix=prefix)
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
            unfiltered_claims=True,
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

    telemetry_before = await read_redis_telemetry(client) if redis_telemetry else None
    wall_start = time.perf_counter()
    await pool.start()
    try:
        deadline = wall_start + max(10.0, jobs * max(handler_delay_seconds, 0.01) * 3)
        final_jobs = []
        while True:
            final_jobs = [await store.get(job_id) for job_id in submitted_at]
            if all(
                job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}
                for job in final_jobs
            ):
                break
            if time.perf_counter() >= deadline:
                raise TimeoutError("durable scale scenario did not finish")
            await asyncio.sleep(0.005)
    finally:
        await pool.stop(graceful_timeout_seconds=1.0)

    elapsed = time.perf_counter() - wall_start
    completed = sum(job.status is JobStatus.SUCCEEDED for job in final_jobs)
    true_errors = sum(job.status is not JobStatus.SUCCEEDED for job in final_jobs)
    telemetry_after = await read_redis_telemetry(client) if redis_telemetry else None
    await client.aclose()

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
        redis_telemetry=(
            diff_redis_telemetry(telemetry_before, telemetry_after, completed=completed)
            if telemetry_before is not None and telemetry_after is not None
            else None
        ),
    )


async def run_scale_trials(
    *,
    redis_url: str,
    workers: int,
    jobs: int,
    handler_delay_seconds: float,
    repetitions: int,
    redis_telemetry: bool = False,
) -> ScaleSummary:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    trials = [
        await run_scale_scenario(
            redis_url=redis_url,
            workers=workers,
            jobs=jobs,
            handler_delay_seconds=handler_delay_seconds,
            redis_telemetry=redis_telemetry,
        )
        for _ in range(repetitions)
    ]
    return summarize_trials(trials)


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6379/15")
    parser.add_argument("--workers", default="1,2,4")
    parser.add_argument("--jobs", type=int, default=48)
    parser.add_argument("--handler-delay-ms", type=float, default=20.0)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--redis-telemetry", action="store_true")
    args = parser.parse_args()

    summaries = []
    for workers in [int(value) for value in args.workers.split(",") if value.strip()]:
        summaries.append(
            await run_scale_trials(
                redis_url=args.redis_url,
                workers=workers,
                jobs=args.jobs,
                handler_delay_seconds=args.handler_delay_ms / 1000,
                repetitions=args.repetitions,
                redis_telemetry=args.redis_telemetry,
            )
        )
    print(json.dumps([asdict(summary) for summary in summaries], indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(_main())
