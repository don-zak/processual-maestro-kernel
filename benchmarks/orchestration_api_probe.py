from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx


@dataclass(slots=True)
class OrchestrationAPIResult:
    workers: int
    width: int
    concurrency: int
    requests: int
    success: int
    backpressure: int
    errors: int
    duration_seconds: float
    successful_rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    backpressure_rate: float
    error_rate: float


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(math.ceil(q * len(ordered)) - 1, len(ordered) - 1)
    return ordered[max(index, 0)]


def classify_response(response: httpx.Response) -> str:
    if 200 <= response.status_code < 300:
        return "success"
    if (
        response.status_code == 429
        and response.headers.get("X-Maestro-Capacity-Reason") == "execution_fanout"
    ):
        return "backpressure"
    return "error"


async def run_stage(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    workers: int,
    width: int,
    concurrency: int,
    requests: int,
) -> OrchestrationAPIResult:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    success = 0
    backpressure = 0
    errors = 0

    async def one(request_id: int) -> None:
        nonlocal success, backpressure, errors
        async with semaphore:
            started = time.perf_counter()
            try:
                response = await client.post(
                    f"{base_url}/workflows/llm-orchestration",
                    json={
                        "provider": "benchmark-orchestration",
                        "prompts": [
                            f"request-{request_id}-slot-{slot}"
                            for slot in range(width)
                        ],
                    },
                )
                outcome = classify_response(response)
                if outcome == "success":
                    success += 1
                elif outcome == "backpressure":
                    backpressure += 1
                else:
                    errors += 1
            except Exception:
                errors += 1
            finally:
                latencies.append((time.perf_counter() - started) * 1000)

    started = time.perf_counter()
    await asyncio.gather(*(one(request_id) for request_id in range(requests)))
    duration = time.perf_counter() - started
    return OrchestrationAPIResult(
        workers=workers,
        width=width,
        concurrency=concurrency,
        requests=requests,
        success=success,
        backpressure=backpressure,
        errors=errors,
        duration_seconds=round(duration, 4),
        successful_rps=round(success / duration, 2),
        p50_ms=round(statistics.median(latencies), 2),
        p95_ms=round(percentile(latencies, 0.95), 2),
        p99_ms=round(percentile(latencies, 0.99), 2),
        backpressure_rate=backpressure / requests,
        error_rate=errors / requests,
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8030")
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--widths", default="4,8,12,16")
    parser.add_argument("--concurrency", default="5,10,20,40")
    parser.add_argument("--requests", type=int, default=80)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    widths = [int(value) for value in args.widths.split(",") if value.strip()]
    stages = [int(value) for value in args.concurrency.split(",") if value.strip()]
    limits = httpx.Limits(max_connections=max(stages) * 3, max_keepalive_connections=max(stages))
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        results = [
            await run_stage(
                client=client,
                base_url=args.base_url.rstrip("/"),
                workers=args.workers,
                width=width,
                concurrency=concurrency,
                requests=args.requests,
            )
            for width in widths
            for concurrency in stages
        ]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps([asdict(result) for result in results], indent=2) + "\n",
        encoding="utf-8",
    )

    print("| Workers | Width | Concurrency | p95 ms | Successful RPS | Backpressure | Errors |")
    print("|---:|---:|---:|---:|---:|---:|---:|")
    for result in results:
        print(
            f"| {result.workers} | {result.width} | {result.concurrency} | "
            f"{result.p95_ms:.2f} | {result.successful_rps:.2f} | "
            f"{result.backpressure_rate:.2%} | {result.error_rate:.2%} |"
        )

    violations = [result for result in results if result.error_rate > args.max_error_rate]
    if violations:
        raise SystemExit(
            "orchestration API true error rate exceeded "
            f"{args.max_error_rate:.2%}"
        )


if __name__ == "__main__":
    asyncio.run(main())
