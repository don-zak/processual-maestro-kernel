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


def workflow_payload(index: int, *, step_count: int, label: str) -> tuple[str, dict[str, object], dict[str, str]]:
    token = uuid.uuid4().hex
    steps = [
        {
            "id": f"{label}-step-{index}-{step_index}",
            "agent_type": "work",
            "description": f"{label} benchmark workflow step " + ("x" * 96),
        }
        for step_index in range(step_count)
    ]
    return (
        "/workflows",
        {
            "workflow_id": f"{label}-load-{index}-{token}",
            "goal": f"benchmark {label} workflow creation",
            "steps": steps,
        },
        {"X-API-Key": "benchmark-only-api-key"},
    )


def governance_payload(index: int, *, batch_size: int = 20) -> tuple[str, dict[str, object], dict[str, str]]:
    answers = []
    for item in range(batch_size):
        answers.append(
            {
                "answer": f"Deterministic benchmark answer {index}-{item}. " + ("stable context " * 12),
                "language": "en",
                "compatibility": 0.72,
                "coherence": 0.78,
                "structural_support": 0.68,
                "usefulness": 0.81,
                "complexity": 0.34,
                "fatigue": 0.12,
                "shock": 0.08,
                "lift": 0.64,
                "novelty": 0.43,
                "no_answer": 0.0,
                "hallucination": 0.03,
                "constraint_failure": 0.01,
                "speed": 0.74,
            }
        )
    return (
        "/cgt/govern/batch",
        {"answers": answers},
        {"X-API-Key": "benchmark-only-api-key"},
    )


def payload_for(workload: str, index: int) -> tuple[str, dict[str, object] | None, dict[str, str]]:
    if workload == "light":
        return "/health/live", None, {}
    if workload == "normal":
        return workflow_payload(index, step_count=12, label="normal")
    if workload == "heavy":
        return workflow_payload(index, step_count=120, label="heavy")
    if workload == "governance-heavy":
        return governance_payload(index)
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
    parser.add_argument("--governance-requests", type=int, default=40)
    args = parser.parse_args()

    stages = [int(value) for value in args.concurrency.split(",") if value.strip()]
    request_counts = {
        "light": args.light_requests,
        "normal": args.normal_requests,
        "heavy": args.heavy_requests,
        "governance-heavy": args.governance_requests,
    }
    limits = httpx.Limits(max_connections=max(stages) * 3, max_keepalive_connections=max(stages))
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        results_by_workload: dict[str, list[Result]] = {}
        for workload in ("light", "normal", "heavy", "governance-heavy"):
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
