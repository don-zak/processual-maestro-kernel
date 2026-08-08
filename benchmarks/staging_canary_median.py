from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

try:
    from benchmarks.staging_canary_gate import (
        CanaryGateResult,
        evaluate_canary_gate,
        markdown,
    )
except ModuleNotFoundError:
    from staging_canary_gate import CanaryGateResult, evaluate_canary_gate, markdown


WORKLOADS = ("normal", "heavy", "governance-heavy")
WORKLOAD_METRICS = (
    "p95_ms",
    "admitted_ocu_per_second",
    "backpressure_rate",
    "error_rate",
)
EXECUTION_METRICS = (
    "p95_ms",
    "successful_rps",
    "backpressure_rate",
    "error_rate",
)


def _median(values: list[float]) -> float:
    if not values:
        raise ValueError("median requires at least one value")
    return float(statistics.median(values))


def _workload_stage(payload: dict[str, Any], workload: str, concurrency: int) -> dict[str, Any]:
    rows = payload.get(workload, {}).get("results", [])
    for row in rows:
        if int(row.get("concurrency", -1)) == concurrency:
            return row
    raise ValueError(f"missing {workload}@c{concurrency} workload stage")


def aggregate_workload_trials(
    trials: list[dict[str, Any]],
    *,
    concurrency: int = 40,
) -> dict[str, Any]:
    if len(trials) < 3:
        raise ValueError("at least three workload trials are required")

    aggregated: dict[str, Any] = {}
    for workload in WORKLOADS:
        rows = [_workload_stage(trial, workload, concurrency) for trial in trials]
        median_row: dict[str, Any] = {"concurrency": concurrency}
        for metric in WORKLOAD_METRICS:
            median_row[metric] = _median([float(row[metric]) for row in rows])
        aggregated[workload] = {"results": [median_row]}
    return aggregated


def _execution_stage(
    payload: list[dict[str, Any]],
    *,
    providers: int,
    width: int,
    concurrency: int,
) -> dict[str, Any]:
    for row in payload:
        if (
            int(row.get("providers", -1)) == providers
            and int(row.get("width", -1)) == width
            and int(row.get("concurrency", -1)) == concurrency
        ):
            return row
    raise ValueError(
        f"missing execution stage providers={providers}/width={width}/c{concurrency}"
    )


def aggregate_execution_trials(
    trials: list[list[dict[str, Any]]],
    *,
    workers: int,
    concurrency: int = 40,
) -> list[dict[str, Any]]:
    if len(trials) < 3:
        raise ValueError("at least three execution-mix trials are required")

    aggregated: list[dict[str, Any]] = []
    for width in (4, 8):
        rows = [
            _execution_stage(
                trial,
                providers=2,
                width=width,
                concurrency=concurrency,
            )
            for trial in trials
        ]
        median_row: dict[str, Any] = {
            "workers": workers,
            "providers": 2,
            "width": width,
            "concurrency": concurrency,
        }
        for metric in EXECUTION_METRICS:
            median_row[metric] = _median([float(row[metric]) for row in rows])
        aggregated.append(median_row)
    return aggregated


def evaluate_median_canary(
    workload_trials_1w: list[dict[str, Any]],
    workload_trials_2w: list[dict[str, Any]],
    execution_trials_1w: list[list[dict[str, Any]]],
    execution_trials_2w: list[list[dict[str, Any]]],
    *,
    concurrency: int = 40,
) -> CanaryGateResult:
    return evaluate_canary_gate(
        aggregate_workload_trials(workload_trials_1w, concurrency=concurrency),
        aggregate_workload_trials(workload_trials_2w, concurrency=concurrency),
        aggregate_execution_trials(
            execution_trials_1w,
            workers=1,
            concurrency=concurrency,
        ),
        aggregate_execution_trials(
            execution_trials_2w,
            workers=2,
            concurrency=concurrency,
        ),
        concurrency=concurrency,
    )


def _load_json(paths: list[str]) -> list[Any]:
    return [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]


def promotion_scope(result: CanaryGateResult) -> str:
    if result.passed:
        return (
            "Promotion scope: **2 workers are qualified for staging/canary only.** "
            "Production remains at the existing 1-worker default until a separate "
            "production promotion decision is made."
        )
    return (
        "Promotion scope: **2 workers are not qualified for staging/canary.** "
        "Production remains at the existing 1-worker default."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workloads-1w", nargs="+", required=True)
    parser.add_argument("--workloads-2w", nargs="+", required=True)
    parser.add_argument("--execution-mix-1w", nargs="+", required=True)
    parser.add_argument("--execution-mix-2w", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--concurrency", type=int, default=40)
    args = parser.parse_args()

    counts = {
        len(args.workloads_1w),
        len(args.workloads_2w),
        len(args.execution_mix_1w),
        len(args.execution_mix_2w),
    }
    if len(counts) != 1 or next(iter(counts)) < 3:
        raise SystemExit("all canary inputs must contain the same number of at least three trials")

    result = evaluate_median_canary(
        _load_json(args.workloads_1w),
        _load_json(args.workloads_2w),
        _load_json(args.execution_mix_1w),
        _load_json(args.execution_mix_2w),
        concurrency=args.concurrency,
    )
    report = markdown(result).replace(
        "# Two-worker staging/canary gate",
        "# Two-worker staging/canary median gate",
        1,
    )
    report += f"\n\nTrials per topology: **{len(args.workloads_1w)}**."
    report += f"\n\n{promotion_scope(result)}"

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
