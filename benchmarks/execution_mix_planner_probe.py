from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx


@dataclass(slots=True)
class PlannerResult:
    planner: bool
    providers: int
    width: int
    concurrency: int
    requests: int
    success: int
    backpressure: int
    errors: int
    successful_rps: float
    p95_ms: float
    backpressure_rate: float
    error_rate: float


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(math.ceil(q * len(ordered)) - 1, len(ordered) - 1)
    return ordered[max(index, 0)]


async def run_stage(
    client: httpx.AsyncClient,
    base_url: str,
    *,
    planner: bool,
    providers: int,
    width: int,
    concurrency: int,
    requests: int,
) -> PlannerResult:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    success = backpressure = errors = 0

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
                        "use_planner": str(planner).lower(),
                    },
                )
                if 200 <= response.status_code < 300:
                    success += 1
                elif response.status_code == 429:
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
    return PlannerResult(
        planner=planner,
        providers=providers,
        width=width,
        concurrency=concurrency,
        requests=requests,
        success=success,
        backpressure=backpressure,
        errors=errors,
        successful_rps=round(success / duration, 2),
        p95_ms=round(percentile(latencies, 0.95), 2),
        backpressure_rate=backpressure / requests,
        error_rate=errors / requests,
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8020")
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    matrix = [(1, 8), (1, 16), (2, 8), (2, 16)]
    concurrencies = [20, 40]
    async with httpx.AsyncClient(timeout=30.0) as client:
        results = [
            await run_stage(
                client,
                args.base_url.rstrip("/"),
                planner=planner,
                providers=providers,
                width=width,
                concurrency=concurrency,
                requests=args.requests,
            )
            for planner in (False, True)
            for providers, width in matrix
            for concurrency in concurrencies
        ]

    Path(args.output).write_text(
        json.dumps([asdict(result) for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    print("| Planner | Providers | Width | C | p95 ms | Success RPS | BP | Errors |")
    print("|:---:|---:|---:|---:|---:|---:|---:|---:|")
    for result in results:
        print(
            f"| {result.planner} | {result.providers} | {result.width} | "
            f"{result.concurrency} | {result.p95_ms:.2f} | "
            f"{result.successful_rps:.2f} | {result.backpressure_rate:.2%} | "
            f"{result.error_rate:.2%} |"
        )

    if any(result.errors for result in results):
        raise SystemExit("planner benchmark observed true execution errors")


if __name__ == "__main__":
    asyncio.run(main())
