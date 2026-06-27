from __future__ import annotations

import math
from dataclasses import dataclass, replace
from itertools import product

from .benchmark_surfaces import BenchmarkSurface, evaluate_benchmark_surfaces, summarize_benchmark_surface
from .scenarios import ScenarioPack
from .sensitivity import SensitivityReport, evaluate_parameter_sensitivity, summarize_sensitivity_report
from .types import CGTParameters
from .validation import ensure_not_empty


@dataclass(frozen=True, slots=True)
class RobustnessReport:
    parameter_grid: tuple[CGTParameters, ...]
    sensitivity: SensitivityReport
    surfaces: tuple[BenchmarkSurface, ...]
    axis_names: tuple[str, ...]


def _build_parameter_grid(
    base_parameters: CGTParameters, axis_grids: dict[str, tuple[float, ...]]
) -> tuple[CGTParameters, ...]:
    axis_names = tuple(axis_grids.keys())
    ensure_not_empty(axis_names, "axis_grids")
    axis_values_product = product(*(axis_grids[name] for name in axis_names))
    return tuple(
        replace(
            base_parameters, **{axis_name: float(axis_value) for axis_name, axis_value in zip(axis_names, axis_values)}
        )
        for axis_values in axis_values_product
    )


def evaluate_multi_axis_robustness(
    packs: list[ScenarioPack],
    *,
    base_parameters: CGTParameters,
    axis_grids: dict[str, tuple[float, ...]],
) -> RobustnessReport:
    ensure_not_empty(packs, "packs")
    ensure_not_empty(list(axis_grids.keys()), "axis_grids")
    parameter_grid = _build_parameter_grid(base_parameters, axis_grids)
    sensitivity = evaluate_parameter_sensitivity(packs, list(parameter_grid))
    surfaces = evaluate_benchmark_surfaces(packs, base_parameters=base_parameters, axis_grids=axis_grids)
    return RobustnessReport(
        parameter_grid=parameter_grid,
        sensitivity=sensitivity,
        surfaces=surfaces,
        axis_names=tuple(axis_grids.keys()),
    )


def summarize_robustness_report(report: RobustnessReport) -> dict[str, float]:
    sensitivity_summary = summarize_sensitivity_report(report.sensitivity)
    ensure_not_empty(report.surfaces, "report.surfaces")
    transition_spans = []
    compatibility_spans = []
    aftermath_spans = []
    for surface in report.surfaces:
        summary = summarize_benchmark_surface(surface)
        transition_spans.append(summary["mean_transition_channel_span"])
        compatibility_spans.append(summary["mean_compatibility_span"])
        aftermath_spans.append(summary["mean_aftermath_balance_span"])
    return {
        "grid_size": float(len(report.parameter_grid)),
        "axis_count": float(len(report.axis_names)),
        "surface_count": float(len(report.surfaces)),
        "max_surface_transition_span": max(transition_spans),
        "max_surface_compatibility_span": max(compatibility_spans),
        "max_surface_aftermath_balance_span": max(aftermath_spans),
        "surface_transition_span_center": math.fsum(transition_spans) / len(transition_spans),
        "surface_compatibility_span_center": math.fsum(compatibility_spans) / len(compatibility_spans),
        "surface_aftermath_balance_span_center": math.fsum(aftermath_spans) / len(aftermath_spans),
        **sensitivity_summary,
    }
