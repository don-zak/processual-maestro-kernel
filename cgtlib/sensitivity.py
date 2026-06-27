from __future__ import annotations

import math
from dataclasses import dataclass

from .scenarios import evaluate_scenario_packs, summarize_scenario_packs
from .types import CGTParameters
from .validation import ensure_not_empty


@dataclass(frozen=True, slots=True)
class SensitivitySnapshot:
    parameters: CGTParameters
    summary: dict[str, float]
    per_scenario_transition_means: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class SensitivityReport:
    snapshots: tuple[SensitivitySnapshot, ...]
    metric_spans: dict[str, float]
    max_transition_span: float


def evaluate_parameter_sensitivity(packs: list[object], parameter_grid: list[CGTParameters]) -> SensitivityReport:
    ensure_not_empty(packs, "packs")
    ensure_not_empty(parameter_grid, "parameter_grid")
    snapshots: list[SensitivitySnapshot] = []
    for params in parameter_grid:
        results = evaluate_scenario_packs(packs, params)
        summary = summarize_scenario_packs(results)
        per_scenario_transition_means = tuple(result.summary["average_transition_channel"] for result in results)
        snapshots.append(
            SensitivitySnapshot(
                parameters=params,
                summary=summary,
                per_scenario_transition_means=per_scenario_transition_means,
            )
        )
    metric_spans = _compute_metric_spans(snapshots)
    max_transition_span = _compute_max_transition_span(snapshots)
    return SensitivityReport(
        snapshots=tuple(snapshots),
        metric_spans=metric_spans,
        max_transition_span=max_transition_span,
    )


def _compute_metric_spans(snapshots: list[SensitivitySnapshot]) -> dict[str, float]:
    metric_names = (
        "mean_transition_channel",
        "mean_compatibility",
        "mean_aftermath_balance",
    )
    spans: dict[str, float] = {}
    for name in metric_names:
        values = [snapshot.summary[name] for snapshot in snapshots]
        spans[f"{name}_span"] = max(values) - min(values)
    return spans


def _compute_max_transition_span(snapshots: list[SensitivitySnapshot]) -> float:
    scenario_count = len(snapshots[0].per_scenario_transition_means)
    per_index_spans: list[float] = []
    for index in range(scenario_count):
        values = [snapshot.per_scenario_transition_means[index] for snapshot in snapshots]
        per_index_spans.append(max(values) - min(values))
    return max(per_index_spans, default=0.0)


def summarize_sensitivity_report(report: SensitivityReport) -> dict[str, float]:
    ensure_not_empty(report.snapshots, "report.snapshots")
    mean_transition_values = [snapshot.summary["mean_transition_channel"] for snapshot in report.snapshots]
    mean_compatibility_values = [snapshot.summary["mean_compatibility"] for snapshot in report.snapshots]
    mean_aftermath_values = [snapshot.summary["mean_aftermath_balance"] for snapshot in report.snapshots]
    return {
        "grid_size": float(len(report.snapshots)),
        "mean_transition_channel_center": math.fsum(mean_transition_values) / len(mean_transition_values),
        "mean_compatibility_center": math.fsum(mean_compatibility_values) / len(mean_compatibility_values),
        "mean_aftermath_balance_center": math.fsum(mean_aftermath_values) / len(mean_aftermath_values),
        "max_transition_span": report.max_transition_span,
        **report.metric_spans,
    }
