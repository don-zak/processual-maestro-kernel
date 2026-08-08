from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ExecutionMixDelta:
    providers: int
    width: int
    concurrency: int
    one_worker_p95_ms: float
    two_worker_p95_ms: float
    p95_change_pct: float
    one_worker_rps: float
    two_worker_rps: float
    rps_change_pct: float
    one_worker_backpressure_rate: float
    two_worker_backpressure_rate: float
    true_error_rate_max: float


def change_pct(before: float, after: float) -> float:
    if before == 0:
        return 0.0 if after == 0 else 100.0
    return ((after - before) / before) * 100.0


def index_results(payload: list[dict[str, object]]) -> dict[tuple[int, int, int], dict[str, object]]:
    return {
        (
            int(item["providers"]),
            int(item["width"]),
            int(item["concurrency"]),
        ): item
        for item in payload
    }


def compare(
    one_worker: list[dict[str, object]],
    two_workers: list[dict[str, object]],
    *,
    concurrency: int = 40,
) -> list[ExecutionMixDelta]:
    one_index = index_results(one_worker)
    two_index = index_results(two_workers)
    keys = sorted(key for key in one_index if key[2] == concurrency)
    deltas: list[ExecutionMixDelta] = []
    for key in keys:
        if key not in two_index:
            raise ValueError(f"missing two-worker execution-mix stage: {key}")
        before = one_index[key]
        after = two_index[key]
        before_p95 = float(before.get("p95_ms", 0.0))
        after_p95 = float(after.get("p95_ms", 0.0))
        before_rps = float(before.get("throughput_rps", 0.0))
        after_rps = float(after.get("throughput_rps", 0.0))
        before_bp = float(before.get("backpressure_rate", 0.0))
        after_bp = float(after.get("backpressure_rate", 0.0))
        before_errors = float(before.get("error_rate", 0.0))
        after_errors = float(after.get("error_rate", 0.0))
        deltas.append(
            ExecutionMixDelta(
                providers=key[0],
                width=key[1],
                concurrency=key[2],
                one_worker_p95_ms=before_p95,
                two_worker_p95_ms=after_p95,
                p95_change_pct=change_pct(before_p95, after_p95),
                one_worker_rps=before_rps,
                two_worker_rps=after_rps,
                rps_change_pct=change_pct(before_rps, after_rps),
                one_worker_backpressure_rate=before_bp,
                two_worker_backpressure_rate=after_bp,
                true_error_rate_max=max(before_errors, after_errors),
            )
        )
    return deltas


def markdown(deltas: list[ExecutionMixDelta]) -> str:
    lines = [
        "# Deterministic LLM execution-mix comparison",
        "",
        "Positive RPS change is better; negative p95 change is better.",
        "",
        "| Providers | Width | Concurrency | 1w p95 ms | 2w p95 ms | p95 delta | 1w RPS | 2w RPS | RPS delta | 1w BP | 2w BP | Max true errors |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in deltas:
        lines.append(
            f"| {item.providers} | {item.width} | {item.concurrency} | "
            f"{item.one_worker_p95_ms:.2f} | {item.two_worker_p95_ms:.2f} | "
            f"{item.p95_change_pct:+.2f}% | {item.one_worker_rps:.2f} | "
            f"{item.two_worker_rps:.2f} | {item.rps_change_pct:+.2f}% | "
            f"{item.one_worker_backpressure_rate:.2%} | "
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

    if any(item.true_error_rate_max > 0.0 for item in deltas):
        print("Execution-mix comparison rejected: true errors must remain zero.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
