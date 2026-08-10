from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

try:
    from benchmarks.execution_mix_compare import compare as compare_execution_mix
    from benchmarks.topology_compare import compare as compare_topology
except ModuleNotFoundError:
    from execution_mix_compare import compare as compare_execution_mix
    from topology_compare import compare as compare_topology


@dataclass(frozen=True, slots=True)
class CanaryGateResult:
    passed: bool
    violations: tuple[str, ...]


def _gain_pct(before: float, after: float) -> float:
    if before == 0:
        return 0.0 if after == 0 else 100.0
    return ((after - before) / before) * 100.0


def evaluate_canary_gate(
    workloads_1w: dict[str, object],
    workloads_2w: dict[str, object],
    execution_mix_1w: list[dict[str, object]],
    execution_mix_2w: list[dict[str, object]],
    *,
    concurrency: int = 40,
    min_aggregate_ocu_gain_pct: float = 10.0,
    max_workload_ocu_regression_pct: float = 10.0,
    max_p95_regression_pct: float = 10.0,
    max_backpressure_regression: float = 0.05,
    max_true_error_rate: float = 0.01,
    min_execution_success_rps_gain_pct: float = 10.0,
) -> CanaryGateResult:
    violations: list[str] = []

    topology_deltas = compare_topology(
        workloads_1w,
        workloads_2w,
        concurrency=concurrency,
    )
    one_worker_ocu = sum(item.one_worker_ocu_per_second for item in topology_deltas)
    two_worker_ocu = sum(item.two_worker_ocu_per_second for item in topology_deltas)
    aggregate_ocu_gain_pct = _gain_pct(one_worker_ocu, two_worker_ocu)
    if aggregate_ocu_gain_pct < min_aggregate_ocu_gain_pct:
        violations.append(
            "workloads: aggregate OCU/s gain "
            f"{aggregate_ocu_gain_pct:+.2f}% is below "
            f"{min_aggregate_ocu_gain_pct:.2f}%"
        )

    for delta in topology_deltas:
        label = f"{delta.workload}@c{concurrency}"
        if delta.ocu_per_second_change_pct < -max_workload_ocu_regression_pct:
            violations.append(
                f"{label}: OCU/s regression {delta.ocu_per_second_change_pct:+.2f}% "
                f"exceeds {max_workload_ocu_regression_pct:.2f}%"
            )
        if delta.p95_change_pct > max_p95_regression_pct:
            violations.append(
                f"{label}: p95 regression {delta.p95_change_pct:+.2f}% "
                f"exceeds {max_p95_regression_pct:.2f}%"
            )
        if (
            delta.two_worker_backpressure_rate
            - delta.one_worker_backpressure_rate
            > max_backpressure_regression
        ):
            violations.append(
                f"{label}: backpressure regression exceeds "
                f"{max_backpressure_regression:.2%}"
            )
        if delta.true_error_rate_max > max_true_error_rate:
            violations.append(
                f"{label}: true error rate {delta.true_error_rate_max:.2%} "
                f"exceeds {max_true_error_rate:.2%}"
            )

    execution_deltas = compare_execution_mix(
        execution_mix_1w,
        execution_mix_2w,
        concurrency=concurrency,
    )
    canary_execution_deltas = [
        delta
        for delta in execution_deltas
        if delta.providers == 2 and delta.width in {4, 8}
    ]
    if not canary_execution_deltas:
        violations.append("execution mix: missing 2-provider width 4/8 canary stages")
    else:
        one_worker_success = sum(
            delta.one_worker_successful_rps for delta in canary_execution_deltas
        )
        two_worker_success = sum(
            delta.two_worker_successful_rps for delta in canary_execution_deltas
        )
        if one_worker_success <= 0:
            violations.append("execution mix: one-worker successful RPS baseline is zero")
        else:
            successful_rps_gain_pct = _gain_pct(
                one_worker_success,
                two_worker_success,
            )
            if successful_rps_gain_pct < min_execution_success_rps_gain_pct:
                violations.append(
                    "execution mix: aggregate successful RPS gain "
                    f"{successful_rps_gain_pct:+.2f}% is below "
                    f"{min_execution_success_rps_gain_pct:.2f}%"
                )

        for delta in canary_execution_deltas:
            label = f"execution-mix:p{delta.providers}:w{delta.width}:c{concurrency}"
            if (
                delta.two_worker_backpressure_rate
                - delta.one_worker_backpressure_rate
                > max_backpressure_regression
            ):
                violations.append(
                    f"{label}: backpressure regression exceeds "
                    f"{max_backpressure_regression:.2%}"
                )
            if delta.true_error_rate_max > 0.0:
                violations.append(
                    f"{label}: true errors must remain zero, got "
                    f"{delta.true_error_rate_max:.2%}"
                )

    return CanaryGateResult(
        passed=not violations,
        violations=tuple(violations),
    )


def markdown(result: CanaryGateResult) -> str:
    lines = [
        "# Two-worker staging/canary gate",
        "",
        f"Status: **{'PASS' if result.passed else 'FAIL'}**",
        "",
        "Gate policy:",
        "- Aggregate admitted OCU/s across normal/heavy/governance-heavy c40 must gain at least 10%.",
        "- No individual workload may regress more than 10% admitted OCU/s.",
        "- Each workload p95 may regress by at most 10%.",
        "- Backpressure may regress by at most 5 percentage points.",
        "- Workload true errors must remain at or below 1%.",
        "- Aggregate successful RPS for 2-provider width 4/8 execution-mix stages must gain at least 10%.",
        "- Execution-mix true errors must remain zero.",
    ]
    if result.violations:
        lines.extend(["", "Violations:"])
        lines.extend(f"- {violation}" for violation in result.violations)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workloads_1w")
    parser.add_argument("workloads_2w")
    parser.add_argument("execution_mix_1w")
    parser.add_argument("execution_mix_2w")
    parser.add_argument("--output", required=True)
    parser.add_argument("--concurrency", type=int, default=40)
    args = parser.parse_args()

    workloads_1w = json.loads(Path(args.workloads_1w).read_text(encoding="utf-8"))
    workloads_2w = json.loads(Path(args.workloads_2w).read_text(encoding="utf-8"))
    execution_mix_1w = json.loads(
        Path(args.execution_mix_1w).read_text(encoding="utf-8")
    )
    execution_mix_2w = json.loads(
        Path(args.execution_mix_2w).read_text(encoding="utf-8")
    )

    result = evaluate_canary_gate(
        workloads_1w,
        workloads_2w,
        execution_mix_1w,
        execution_mix_2w,
        concurrency=args.concurrency,
    )
    report = markdown(result)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
