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
class StageResult:
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


async def run_stage(
    *,
    client: httpx.AsyncClient,
    url: str,
    concurrency: int,
    request_count: int,
) -> StageResult:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    success = 0
    errors = 0

    async def one_request() -> None:
        nonlocal success, errors
        async with semaphore:
            started = time.perf_counter()
            try:
                response = await client.get(url)
                if 200 <= response.status_code < 300:
                    success += 1
                else:
                    errors += 1
            except Exception:
                errors += 1
            finally:
                latencies.append((time.perf_counter() - started) * 1000)

    started = time.perf_counter()
    await asyncio.gather(*(one_request() for _ in range(request_count)))
    elapsed = time.perf_counter() - started
    return StageResult(
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


def classify(results: list[StageResult]) -> tuple[int, int | None]:
    baseline = results[0]
    latency_limit = max(250.0, baseline.p95_ms * 5)
    safe = baseline.concurrency
    saturation: int | None = None
    peak_throughput = baseline.throughput_rps

    for result in results:
        peak_throughput = max(peak_throughput, result.throughput_rps)
        throughput_collapse = (
            peak_throughput > 0
            and result.throughput_rps < peak_throughput * 0.75
            and result.concurrency > baseline.concurrency
        )
        saturated = (
            result.error_rate > 0.01
            or result.p95_ms > latency_limit
            or throughput_collapse
        )
        if saturated:
            saturation = result.concurrency
            break
        safe = result.concurrency
    return safe, saturation


def markdown(name: str, url: str, results: list[StageResult]) -> str:
    safe, saturation = classify(results)
    lines = [
        f"## Maestro load probe: {name}",
        "",
        f"Target: `{url}`",
        "",
        "| Concurrency | Requests | p50 ms | p95 ms | p99 ms | RPS | Error rate |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in results:
        lines.append(
            f"| {item.concurrency} | {item.requests} | {item.p50_ms:.2f} | "
            f"{item.p95_ms:.2f} | {item.p99_ms:.2f} | {item.throughput_rps:.2f} | "
            f"{item.error_rate:.2%} |"
        )
    lines.extend(
        [
            "",
            f"Highest stage below the probe threshold: **{safe} concurrent requests**.",
            (
                f"First approximate saturation stage: **{saturation} concurrent requests**."
                if saturation is not None
                else "No saturation threshold was reached in the configured stages."
            ),
            "",
            "Probe threshold: error rate >1%, p95 > max(250 ms, 5x baseline), "
            "or throughput falls below 75% of the best prior stage.",
        ]
    )
    return "\n".join(lines) + "\n"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--path", default="/health/live")
    parser.add_argument("--name", default="probe")
    parser.add_argument("--concurrency", default="1,5,10,20,40,80")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    stages = [int(value) for value in args.concurrency.split(",") if value.strip()]
    url = f"{args.base_url.rstrip('/')}/{args.path.lstrip('/')}"
    limits = httpx.Limits(
        max_connections=max(stages) * 2,
        max_keepalive_connections=max(stages),
    )
    async with httpx.AsyncClient(timeout=args.timeout, limits=limits) as client:
        for _ in range(args.warmup):
            response = await client.get(url)
            response.raise_for_status()

        results = [
            await run_stage(
                client=client,
                url=url,
                concurrency=concurrency,
                request_count=args.requests,
            )
            for concurrency in stages
        ]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": args.name,
        "url": url,
        "safe_concurrency": classify(results)[0],
        "saturation_concurrency": classify(results)[1],
        "results": [asdict(item) for item in results],
    }
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(
        markdown(args.name, url, results),
        encoding="utf-8",
    )
    print(markdown(args.name, url, results))


if __name__ == "__main__":
    asyncio.run(main())
