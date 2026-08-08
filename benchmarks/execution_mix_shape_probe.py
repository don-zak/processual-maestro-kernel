from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx


@dataclass(slots=True)
class ExecutionMixShapeResult:
    local_parallelism: int
    providers: int
    width: int
    concurrency: int
    requests: int
    success: int
    backpressure: int
    errors: int
    duration_seconds: float
    successful_rps: float
    p95_ms: float
    backpressure_rate: float
    error_rate: float
    error_details: dict[str, int] = field(default_factory=dict)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(math.ceil(q * len(ordered)) - 1, len(ordered) - 1)
    return ordered[max(index, 0)]


def increment(details: dict[str, int], key: str) -> None:
    details[key] = details.get(key, 0) + 1


async def run_stage(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    local_parallelism: int,
    providers: int,
    width: int,
    concurrency: int,
    requests: int,
) -> ExecutionMixShapeResult:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    success = 0
    backpressure = 0
    errors = 0
    error_details: dict[str, int] = {}

    async def one(request_id: int) -> None:
        nonlocal success, backpressure, errors
        async with semaphore:
            started = time.perf_counter()
            try:
                response = await client.post(
                    f"{base_url}/benchmark/execution-mix",
                    params={
                        "request_id": request_id,
                        "width": width,
                        "providers": providers,
                        "local_parallelism": local_parallelism,
                    },
                    headers={"X-API-Key": "benchmark-only-api-key"},
                )
                if 200 <= response.status_code < 300:
                    success += 1
                elif response.status_code == 429 and response.headers.get(
                    "X-Maestro-Capacity-Reason"
                ):
                    backpressure += 1
                else:
                    errors += 1
                    increment(error_details, f"status:{response.status_code}")
            except Exception as exc:
                errors += 1
                increment(error_details, f"exception:{type(exc).__name__}")
            finally:
                latencies.append((time.perf_counter() - started) * 1000)

    started = time.perf_counter()
    await asyncio.gather(*(one(request_id) for request_id in range(requests)))
    duration = time.perf_counter() - started
    return ExecutionMixShapeResult(
        local_parallelism=local_parallelism,
        providers=providers,
        width=width,
        concurrency=concurrency,
        requests=requests,
        success=success,
        backpressure=backpressure,
        errors=errors,
        duration_seconds=round(duration, 4),
        successful_rps=round(success / duration, 2),
        p95_ms=round(percentile(latencies, 0.95), 2),
        backpressure_rate=backpressure / requests,
        error_rate=errors / requests,
        error_details=error_details,
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8020")
    parser.add_argument("--local-parallelism", default="0,2,4,8")
    parser.add_argument("--providers", default="1,2")
    parser.add_argument("--widths", default="8,16")
    parser.add_argument("--concurrency", default="20,40")
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    local_limits = [int(value) for value in args.local_parallelism.split(",") if value.strip()]
    provider_counts = [int(value) for value in args.providers.split(",") if value.strip()]
    widths = [int(value) for value in args.widths.split(",") if value.strip()]
    stages = [int(value) for value in args.concurrency.split(",") if value.strip()]
    limits = httpx.Limits(max_connections=max(stages) * 3, max_keepalive_connections=max(stages))
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        results = [
            await run_stage(
                client=client,
                base_url=args.base_url.rstrip("/"),
                local_parallelism=local_parallelism,
                providers=providers,
                width=width,
                concurrency=concurrency,
                requests=args.requests,
            )
            for local_parallelism in local_limits
            for providers in provider_counts
            for width in widths
            for concurrency in stages
        ]

    payload = [asdict(result) for result in results]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print("| Local | Providers | Width | Concurrency | p95 ms | Success RPS | BP | Errors |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for result in results:
        print(
            f"| {result.local_parallelism} | {result.providers} | {result.width} | "
            f"{result.concurrency} | {result.p95_ms:.2f} | {result.successful_rps:.2f} | "
            f"{result.backpressure_rate:.2%} | {result.error_rate:.2%} |"
        )

    violations = [result for result in results if result.error_rate > args.max_error_rate]
    if violations:
        details = ", ".join(
            f"local={result.local_parallelism}/providers={result.providers}/"
            f"width={result.width}/concurrency={result.concurrency}:"
            f"{result.error_rate:.2%} {result.error_details}"
            for result in violations
        )
        raise SystemExit(
            f"execution mix shaping true error rate exceeded {args.max_error_rate:.2%}: {details}"
        )


if __name__ == "__main__":
    asyncio.run(main())
