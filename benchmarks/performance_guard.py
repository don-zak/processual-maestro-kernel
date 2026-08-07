from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StageBudget:
    workload: str
    concurrency: int
    max_p95_ms: float
    min_admitted_ocu_per_second: float = 0.0
    max_backpressure_rate: float = 1.0
    max_error_rate: float = 0.01


BUDGETS = (
    StageBudget("light", 40, max_p95_ms=350.0),
    StageBudget(
        "normal",
        20,
        max_p95_ms=450.0,
        min_admitted_ocu_per_second=300.0,
        max_backpressure_rate=0.25,
    ),
    StageBudget(
        "normal",
        40,
        max_p95_ms=550.0,
        min_admitted_ocu_per_second=300.0,
        max_backpressure_rate=0.35,
    ),
    StageBudget(
        "heavy",
        20,
        max_p95_ms=400.0,
        min_admitted_ocu_per_second=350.0,
    ),
    StageBudget(
        "heavy",
        40,
        max_p95_ms=650.0,
        min_admitted_ocu_per_second=300.0,
    ),
    StageBudget(
        "governance-heavy",
        20,
        max_p95_ms=450.0,
        min_admitted_ocu_per_second=300.0,
        max_backpressure_rate=0.35,
    ),
    StageBudget(
        "governance-heavy",
        40,
        max_p95_ms=600.0,
        min_admitted_ocu_per_second=300.0,
        max_backpressure_rate=0.40,
    ),
)

MIN_SATURATION_CONCURRENCY = {
    "normal": 20,
    "heavy": 20,
    "governance-heavy": 20,
}


def _stage(payload: dict[str, object], budget: StageBudget) -> dict[str, object] | None:
    workload_payload = payload.get(budget.workload)
    if not isinstance(workload_payload, dict):
        return None
    results = workload_payload.get("results")
    if not isinstance(results, list):
        return None
    for result in results:
        if isinstance(result, dict) and result.get("concurrency") == budget.concurrency:
            return result
    return None


def evaluate(payload: dict[str, object]) -> list[str]:
    """Return deterministic performance-budget violations."""

    violations: list[str] = []
    for budget in BUDGETS:
        result = _stage(payload, budget)
        label = f"{budget.workload}@{budget.concurrency}"
        if result is None:
            violations.append(f"{label}: benchmark stage missing")
            continue

        p95_ms = float(result.get("p95_ms", 0.0))
        admitted_rate = float(result.get("admitted_ocu_per_second", 0.0))
        backpressure_rate = float(result.get("backpressure_rate", 0.0))
        error_rate = float(result.get("error_rate", 0.0))

        if p95_ms > budget.max_p95_ms:
            violations.append(
                f"{label}: p95 {p95_ms:.2f}ms exceeds {budget.max_p95_ms:.2f}ms"
            )
        if admitted_rate < budget.min_admitted_ocu_per_second:
            violations.append(
                f"{label}: admitted OCU/s {admitted_rate:.2f} below "
                f"{budget.min_admitted_ocu_per_second:.2f}"
            )
        if backpressure_rate > budget.max_backpressure_rate:
            violations.append(
                f"{label}: backpressure {backpressure_rate:.2%} exceeds "
                f"{budget.max_backpressure_rate:.2%}"
            )
        if error_rate > budget.max_error_rate:
            violations.append(
                f"{label}: true error rate {error_rate:.2%} exceeds "
                f"{budget.max_error_rate:.2%}"
            )

    for workload, minimum in MIN_SATURATION_CONCURRENCY.items():
        workload_payload = payload.get(workload)
        if not isinstance(workload_payload, dict):
            violations.append(f"{workload}: workload missing")
            continue
        saturation = workload_payload.get("saturation_concurrency")
        if saturation is not None and int(saturation) < minimum:
            violations.append(
                f"{workload}: saturation starts at {saturation}, below {minimum}"
            )

    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results")
    args = parser.parse_args()

    payload = json.loads(Path(args.results).read_text(encoding="utf-8"))
    violations = evaluate(payload)
    if violations:
        print("Performance regression guard failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Performance regression guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
