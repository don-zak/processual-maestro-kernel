from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from benchmarks.orchestration_api_probe import OrchestrationAPIResult, run_stage


@dataclass(slots=True)
class OrchestrationSoakSummary:
    width: int
    concurrency: int
    trials: int
    requests_per_trial: int
    total_requests: int
    median_successful_rps: float
    median_p95_ms: float
    max_backpressure_rate: float
    total_errors: int


def summarize_results(
    results: list[OrchestrationAPIResult],
) -> list[OrchestrationSoakSummary]:
    grouped: dict[tuple[int, int], list[OrchestrationAPIResult]] = {}
    for result in results:
        grouped.setdefault((result.width, result.concurrency), []).append(result)

    summaries: list[OrchestrationSoakSummary] = []
    for (width, concurrency), trials in sorted(grouped.items()):
        requests_per_trial = trials[0].requests if trials else 0
        summaries.append(
            OrchestrationSoakSummary(
                width=width,
                concurrency=concurrency,
                trials=len(trials),
                requests_per_trial=requests_per_trial,
                total_requests=sum(result.requests for result in trials),
                median_successful_rps=round(
                    statistics.median(result.successful_rps for result in trials),
                    2,
                ),
                median_p95_ms=round(
                    statistics.median(result.p95_ms for result in trials),
                    2,
                ),
                max_backpressure_rate=max(
                    (result.backpressure_rate for result in trials),
                    default=0.0,
                ),
                total_errors=sum(result.errors for result in trials),
            )
        )
    return summaries


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8030")
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--widths", default="4,8,12,16")
    parser.add_argument("--concurrency", default="10,20")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--requests", type=int, default=120)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.trials < 1:
        raise SystemExit("trials must be at least 1")
    if args.requests < 1:
        raise SystemExit("requests must be at least 1")

    widths = [int(value) for value in args.widths.split(",") if value.strip()]
    concurrency_levels = [
        int(value) for value in args.concurrency.split(",") if value.strip()
    ]
    limits = httpx.Limits(
        max_connections=max(concurrency_levels) * 3,
        max_keepalive_connections=max(concurrency_levels),
    )

    results: list[OrchestrationAPIResult] = []
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        for width in widths:
            for concurrency in concurrency_levels:
                for _trial in range(args.trials):
                    results.append(
                        await run_stage(
                            client=client,
                            base_url=args.base_url.rstrip("/"),
                            workers=args.workers,
                            width=width,
                            concurrency=concurrency,
                            requests=args.requests,
                        )
                    )

    summaries = summarize_results(results)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "trials": [asdict(result) for result in results],
                "summaries": [asdict(summary) for summary in summaries],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "| Width | Concurrency | Trials | Requests | Median RPS | Median p95 ms | "
        "Max BP | Errors |"
    )
    print("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for summary in summaries:
        print(
            f"| {summary.width} | {summary.concurrency} | {summary.trials} | "
            f"{summary.total_requests} | {summary.median_successful_rps:.2f} | "
            f"{summary.median_p95_ms:.2f} | {summary.max_backpressure_rate:.2%} | "
            f"{summary.total_errors} |"
        )

    total_errors = sum(summary.total_errors for summary in summaries)
    if total_errors:
        raise SystemExit(
            f"orchestration API soak observed {total_errors} true errors"
        )


if __name__ == "__main__":
    asyncio.run(main())
