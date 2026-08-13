from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import Mock, call

import pytest

_private_package = ModuleType("cgtlib.private")
_compute_module = ModuleType("cgtlib.private.compute")
_private_package.compute = _compute_module
sys.modules["cgtlib.private"] = _private_package
sys.modules["cgtlib.private.compute"] = _compute_module
try:
    import cgtlib.benchmark_surfaces as benchmark_surfaces
    from cgtlib.benchmark_surfaces import BenchmarkSurface, BenchmarkSurfacePoint
    from cgtlib.types import CGTParameters
finally:
    sys.modules.pop("cgtlib.private.compute", None)
    sys.modules.pop("cgtlib.private", None)


def test_evaluate_benchmark_surface_rejects_invalid_axis() -> None:
    with pytest.raises(ValueError, match="unknown axis 'missing'"):
        benchmark_surfaces.evaluate_benchmark_surface(
            [object()],
            base_parameters=CGTParameters(),
            axis_name="missing",
            axis_values=(1.0,),
        )


def test_evaluate_benchmark_surface_rejects_empty_inputs() -> None:
    with pytest.raises(ValueError):
        benchmark_surfaces.evaluate_benchmark_surface(
            [],
            base_parameters=CGTParameters(),
            axis_name="lam",
            axis_values=(1.0,),
        )

    with pytest.raises(ValueError):
        benchmark_surfaces.evaluate_benchmark_surface(
            [object()],
            base_parameters=CGTParameters(),
            axis_name="lam",
            axis_values=(),
        )


def test_evaluate_benchmark_surface_replaces_axis_and_summarizes_each_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = [object()]
    base = CGTParameters(lam=1.0, omega=2.0)
    evaluate = Mock(side_effect=[["first-result"], ["second-result"]])
    summarize = Mock(
        side_effect=[
            {
                "mean_transition_channel": 0.2,
                "mean_compatibility": 0.3,
                "mean_aftermath_balance": 0.4,
            },
            {
                "mean_transition_channel": 0.8,
                "mean_compatibility": 0.7,
                "mean_aftermath_balance": 0.6,
            },
        ]
    )
    monkeypatch.setattr(benchmark_surfaces, "evaluate_scenario_packs", evaluate)
    monkeypatch.setattr(benchmark_surfaces, "summarize_scenario_packs", summarize)

    surface = benchmark_surfaces.evaluate_benchmark_surface(
        packs,
        base_parameters=base,
        axis_name="lam",
        axis_values=(0.5, 2.5),
    )

    assert surface.axis_name == "lam"
    assert [point.axis_value for point in surface.points] == [0.5, 2.5]
    assert [point.parameters.lam for point in surface.points] == [0.5, 2.5]
    assert [point.parameters.omega for point in surface.points] == [2.0, 2.0]
    assert base.lam == 1.0
    assert evaluate.call_args_list == [
        call(packs, surface.points[0].parameters),
        call(packs, surface.points[1].parameters),
    ]
    assert summarize.call_args_list == [call(["first-result"]), call(["second-result"])]
    assert surface.points[0].summary["mean_transition_channel"] == pytest.approx(0.2)
    assert surface.points[1].summary["mean_transition_channel"] == pytest.approx(0.8)


def test_evaluate_benchmark_surfaces_forwards_each_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    packs = [object()]
    base = CGTParameters()
    fake_surfaces = (
        BenchmarkSurface(axis_name="lam", points=()),
        BenchmarkSurface(axis_name="omega", points=()),
    )
    evaluate = Mock(side_effect=fake_surfaces)
    monkeypatch.setattr(benchmark_surfaces, "evaluate_benchmark_surface", evaluate)

    result = benchmark_surfaces.evaluate_benchmark_surfaces(
        packs,
        base_parameters=base,
        axis_grids={"lam": (0.5, 1.5), "omega": (2.0,)},
    )

    assert result == fake_surfaces
    assert evaluate.call_args_list == [
        call(packs, base_parameters=base, axis_name="lam", axis_values=(0.5, 1.5)),
        call(packs, base_parameters=base, axis_name="omega", axis_values=(2.0,)),
    ]

    with pytest.raises(ValueError):
        benchmark_surfaces.evaluate_benchmark_surfaces(packs, base_parameters=base, axis_grids={})


def test_summarize_benchmark_surface_reports_ranges_and_spans() -> None:
    base = CGTParameters()
    surface = BenchmarkSurface(
        axis_name="lam",
        points=(
            BenchmarkSurfacePoint(
                axis_name="lam",
                axis_value=0.5,
                parameters=base,
                summary={
                    "mean_transition_channel": 0.2,
                    "mean_compatibility": 0.9,
                    "mean_aftermath_balance": -0.1,
                },
            ),
            BenchmarkSurfacePoint(
                axis_name="lam",
                axis_value=2.5,
                parameters=base,
                summary={
                    "mean_transition_channel": 0.8,
                    "mean_compatibility": 0.4,
                    "mean_aftermath_balance": 0.5,
                },
            ),
        ),
    )

    summary = benchmark_surfaces.summarize_benchmark_surface(surface)

    assert summary == {
        "point_count": 2.0,
        "axis_min": 0.5,
        "axis_max": 2.5,
        "mean_transition_channel_min": 0.2,
        "mean_transition_channel_max": 0.8,
        "mean_transition_channel_span": pytest.approx(0.6),
        "mean_compatibility_min": 0.4,
        "mean_compatibility_max": 0.9,
        "mean_compatibility_span": 0.5,
        "mean_aftermath_balance_min": -0.1,
        "mean_aftermath_balance_max": 0.5,
        "mean_aftermath_balance_span": pytest.approx(0.6),
    }


def test_summarize_benchmark_surface_rejects_empty_points() -> None:
    with pytest.raises(ValueError):
        benchmark_surfaces.summarize_benchmark_surface(BenchmarkSurface(axis_name="lam", points=()))
