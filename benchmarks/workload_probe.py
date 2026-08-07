from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx


@dataclass(slots=True)
class Result:
    workload: str
    concurrency: int
    requests: int
    success: int
    errors: int
    error_rate: float
    duration_seconds: float
    throughput_rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(math.ceil(q * len(ordered)) - 1, len(ordered) - 1)
    return ordered[max(index, 0)]


def payload_for(workload: str, index: int) -> tuple[str, dict[str, object] | None, dict[str, str]]:
    if workload == "light":
        return "/health/live", None, {}
    if workload == "normal":
        return (
            "/cgt/evaluate",
            {
                "transition_channel": 0.62,
                "compatibility": 0.71,
                "retention": 0.66,
                "harmony": 0.58,
                "fatigue": 0.24,
                "complexity": 0.41,
                "shock": 0.17,
                "dwell_time": 4.0,
                "carrier": 0.69,
                "diversity": 0.54,
                "novelty": 0.73,
                "lift": 0.08,
            },
            {},
        )
    if workload == "heavy":
        token = uuid.uuid4().hex
        steps = [
            {
                "id": f"step-{index}-{step_index}",
                "agent_type": "work",
                "description": "benchmark workflow step " + ("x" * 96),
            }
            for step_index in range(120)
        ]
        return (
            "/workflows",
            {
                "workflow_id": f"load-{index}-{token}",
                "goal": "benchmark realistic workflow creation",
                "steps": steps,
            },
            {"X-API-Key": "benchmark-only-api-key"},
        )
    raise ValueError(f"unknown workload: {workload}")


async def run_stage(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    workload: str,
    concurrency: int,
    request_count: int,
) -> Result:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    success = 0
    errors = 0

    async def one(index: int) -> None:
        nonlocal success, errors
        path, payload, headers = payload_for(workload, index)
        async with semaphore:
            started = time.perf_counter()
            try:
                if payload is None:
                    response = await client.get(f"{base_url}{path}", headers=headers)
                else:
                    response = await client.post(f"{base_url}{path}", json=payload, headers=headers)
                if 200 <= response.status_code < 300:
                    success += 1
                else:
                    errors += 1
            except Exception:
                errors += 1
            finally:
                latencies.append((time.perf_counter() - started) * 1000)

    started = time.perf_counter()
    await asyncio.gather(*(one(index) for index in range(request_count)))
    elapsed = time.perf_counter() - started
    return Result(
        workload=workload,
        concurrency=concurrency,
        requests=request_count,
        success=success,
        errors=errors,
        error_rate=errors / request_count,
        duration_seconds=round(elapsed, 4),
        throughput_rps=round(request_count / elapsed, 2),
        p50_ms=round(statistics.median(latencies), 2),
        p95_ms=round(percentile(latencies, 0.95), 2),
        p99_ms=round(percentile(latencies, 0.99), 2),
        max_ms=round(max(latencies), 2),
    )


def first_saturation(results: list[Result]) -> int | None:
    baseline = results[0]
    latency_limit = max(300.0, baseline.p95_ms * 6)
    best_rps = baseline.throughput_rps
    for result in results:
        best_rps = max(best_rps, result.throughput_rps)
        if (
            result.error_rate > 0.01
            or result.p95_ms > latency_limit
            or (
                result.concurrency > baseline.concurrency
                and result.throughput_rps < best_rps * 0.70
            )
        ):
            return result.concurrency
    return None


def markdown(results_by_workload: dict[str, list[Result]]) -> str:
    lines = ["# Maestro realistic workload benchmark", ""]
    for workload, results in results_by_workload.items():
        lines.extend(
            [
                f"## {workload}",
                "",
                "| Concurrency | Requests | p50 ms | p95 ms | p99 ms | RPS | Errors |",
                "|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for result in results:
            lines.append(
                f"| {result.concurrency} | {result.requests} | {result.p50_ms:.2f} | "
                f"{result.p95_ms:.2f} | {result.p99_ms:.2f} | {result.throughput_rps:.2f} | "
                f"{result.error_rate:.2%} |"
            )
        saturation = first_saturation(results)
        lines.extend(
            [
                "",
                (
                    f"Approximate first saturation stage: **{saturation} concurrent requests**."
                    if saturation is not None
                    else "No saturation threshold reached in configured stages."
                ),
                "",
            ]
        )
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", required=True)
    parser.add_argument("--concurrency", default="1,5,10,20,40")
    parser.add_argument("--light-requests", type=int, default=200)
    parser.add_argument("--normal-requests", type=int, default=160)
    parser.add_argument("--heavy-requests", type=int, default=80)
    args = parser.parse_args()

    stages = [int(value) for value in args.concurrency.split(",") if value.strip()]
    request_counts = {
        "light": args.light_requests,
        "normal": args.normal_requests,
        "heavy": args.heavy_requests,
    }
    limits = httpx.Limits(max_connections=max(stages) * 3, max_keepalive_connections=max(stages))
    async with httpx.AsyncClient(timeout=20.0, limits=limits) as client:
        results_by_workload: dict[str, list[Result]] = {}
        for workload in ("light", "normal", "heavy"):
            results_by_workload[workload] = [
                await run_stage(
                    client=client,
                    base_url=args.base_url.rstrip("/"),
                    workload=workload,
                    concurrency=concurrency,
                    request_count=request_counts[workload],
                )
                for concurrency in stages
            ]

    payload = {
        workload: {
            "saturation_concurrency": first_saturation(results),
            "results": [asdict(result) for result in results],
        }
        for workload, results in results_by_workload.items()
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report = markdown(results_by_workload)
    output.with_suffix(".md").write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
