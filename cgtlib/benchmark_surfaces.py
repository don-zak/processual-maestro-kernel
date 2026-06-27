from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from .scenarios import ScenarioPack, evaluate_scenario_packs, summarize_scenario_packs
from .types import CGTParameters
from .validation import ensure_not_empty

_ALLOWED_AXES = frozenset(CGTParameters.__dataclass_fields__.keys())


@dataclass(frozen=True, slots=True)
class BenchmarkSurfacePoint:
    axis_name: str
    axis_value: float
    parameters: CGTParameters
    summary: dict[str, float]


@dataclass(frozen=True, slots=True)
class BenchmarkSurface:
    axis_name: str
    points: tuple[BenchmarkSurfacePoint, ...]


def _ensure_axis_name(axis_name: str) -> str:
    if axis_name not in _ALLOWED_AXES:
        allowed = ", ".join(sorted(_ALLOWED_AXES))
        raise ValueError(f"unknown axis '{axis_name}', expected one of: {allowed}")
    return axis_name


def evaluate_benchmark_surface(
    packs: list[ScenarioPack],
    *,
    base_parameters: CGTParameters,
    axis_name: str,
    axis_values: Iterable[float],
) -> BenchmarkSurface:
    ensure_not_empty(packs, "packs")
    axis_name = _ensure_axis_name(axis_name)
    axis_values_tuple = tuple(float(value) for value in axis_values)
    ensure_not_empty(axis_values_tuple, "axis_values")

    points: list[BenchmarkSurfacePoint] = []
    for axis_value in axis_values_tuple:
        parameters = replace(base_parameters, **{axis_name: axis_value})
        results = evaluate_scenario_packs(packs, parameters)
        summary = summarize_scenario_packs(results)
        points.append(
            BenchmarkSurfacePoint(
                axis_name=axis_name,
                axis_value=axis_value,
                parameters=parameters,
                summary=summary,
            )
        )
    return BenchmarkSurface(axis_name=axis_name, points=tuple(points))


def evaluate_benchmark_surfaces(
    packs: list[ScenarioPack],
    *,
    base_parameters: CGTParameters,
    axis_grids: dict[str, tuple[float, ...]],
) -> tuple[BenchmarkSurface, ...]:
    ensure_not_empty(list(axis_grids.keys()), "axis_grids")
    return tuple(
        evaluate_benchmark_surface(
            packs,
            base_parameters=base_parameters,
            axis_name=axis_name,
            axis_values=axis_values,
        )
        for axis_name, axis_values in axis_grids.items()
    )


def summarize_benchmark_surface(surface: BenchmarkSurface) -> dict[str, float]:
    ensure_not_empty(surface.points, "surface.points")
    transition_values = [point.summary["mean_transition_channel"] for point in surface.points]
    compatibility_values = [point.summary["mean_compatibility"] for point in surface.points]
    aftermath_values = [point.summary["mean_aftermath_balance"] for point in surface.points]
    axis_values = [point.axis_value for point in surface.points]
    return {
        "point_count": float(len(surface.points)),
        "axis_min": min(axis_values),
        "axis_max": max(axis_values),
        "mean_transition_channel_min": min(transition_values),
        "mean_transition_channel_max": max(transition_values),
        "mean_transition_channel_span": max(transition_values) - min(transition_values),
        "mean_compatibility_min": min(compatibility_values),
        "mean_compatibility_max": max(compatibility_values),
        "mean_compatibility_span": max(compatibility_values) - min(compatibility_values),
        "mean_aftermath_balance_min": min(aftermath_values),
        "mean_aftermath_balance_max": max(aftermath_values),
        "mean_aftermath_balance_span": max(aftermath_values) - min(aftermath_values),
    }
