from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TopologyDelta:
    workload: str
    concurrency: int
    one_worker_p95_ms: float
    two_worker_p95_ms: float
    p95_change_pct: float
    one_worker_ocu_per_second: float
    two_worker_ocu_per_second: float
    ocu_per_second_change_pct: float
    one_worker_backpressure_rate: float
    two_worker_backpressure_rate: float
    true_error_rate_max: float


def _change_pct(before: float, after: float) -> float:
    if before == 0:
        return 0.0 if after == 0 else 100.0
    return ((after - before) / before) * 100.0


def _find_stage(payload: dict[str, object], workload: str, concurrency: int) -> dict[str, object]:
    workload_payload = payload.get(workload)
    if not isinstance(workload_payload, dict):
        raise ValueError(f"missing workload: {workload}")
    results = workload_payload.get("results")
    if not isinstance(results, list):
        raise ValueError(f"missing results for workload: {workload}")
    for result in results:
        if isinstance(result, dict) and int(result.get("concurrency", -1)) == concurrency:
            return result
    raise ValueError(f"missing stage: {workload}@{concurrency}")


def compare(
    one_worker: dict[str, object],
    two_workers: dict[str, object],
    *,
    workloads: tuple[str, ...] = ("normal", "heavy", "governance-heavy"),
    concurrency: int = 40,
) -> list[TopologyDelta]:
    deltas: list[TopologyDelta] = []
    for workload in workloads:
        before = _find_stage(one_worker, workload, concurrency)
        after = _find_stage(two_workers, workload, concurrency)
        before_p95 = float(before.get("p95_ms", 0.0))
        after_p95 = float(after.get("p95_ms", 0.0))
        before_ocu = float(before.get("admitted_ocu_per_second", 0.0))
        after_ocu = float(after.get("admitted_ocu_per_second", 0.0))
        before_backpressure = float(before.get("backpressure_rate", 0.0))
        after_backpressure = float(after.get("backpressure_rate", 0.0))
        before_errors = float(before.get("error_rate", 0.0))
        after_errors = float(after.get("error_rate", 0.0))
        deltas.append(
            TopologyDelta(
                workload=workload,
                concurrency=concurrency,
                one_worker_p95_ms=before_p95,
                two_worker_p95_ms=after_p95,
                p95_change_pct=_change_pct(before_p95, after_p95),
                one_worker_ocu_per_second=before_ocu,
                two_worker_ocu_per_second=after_ocu,
                ocu_per_second_change_pct=_change_pct(before_ocu, after_ocu),
                one_worker_backpressure_rate=before_backpressure,
                two_worker_backpressure_rate=after_backpressure,
                true_error_rate_max=max(before_errors, after_errors),
            )
        )
    return deltas


def markdown(deltas: list[TopologyDelta]) -> str:
    header = (
        "| Workload | Concurrency | 1w p95 ms | 2w p95 ms | p95 delta | "
        "1w OCU/s | 2w OCU/s | OCU/s delta | 1w BP | 2w BP | Max true errors |"
    )
    lines = [
        "# Maestro worker topology comparison",
        "",
        "Positive OCU/s change is better; negative p95 change is better.",
        "",
        header,
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in deltas:
        lines.append(
            f"| {item.workload} | {item.concurrency} | {item.one_worker_p95_ms:.2f} | "
            f"{item.two_worker_p95_ms:.2f} | {item.p95_change_pct:+.2f}% | "
            f"{item.one_worker_ocu_per_second:.2f} | {item.two_worker_ocu_per_second:.2f} | "
            f"{item.ocu_per_second_change_pct:+.2f}% | {item.one_worker_backpressure_rate:.2%} | "
            f"{item.two_worker_backpressure_rate:.2%} | {item.true_error_rate_max:.2%} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("one_worker")
    parser.add_argument("two_workers")
    parser.add_argument("--output", required=True)
    parser.add_argument("--concurrency", type=int, default=40)
    args = parser.parse_args()

    one_worker = json.loads(Path(args.one_worker).read_text(encoding="utf-8"))
    two_workers = json.loads(Path(args.two_workers).read_text(encoding="utf-8"))
    deltas = compare(one_worker, two_workers, concurrency=args.concurrency)
    report = markdown(deltas)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report + "\n", encoding="utf-8")
    print(report)

    if any(item.true_error_rate_max > 0.01 for item in deltas):
        print("Topology comparison rejected: true error rate exceeded 1%.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
