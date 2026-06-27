from __future__ import annotations

import math
from dataclasses import dataclass

from .regime_classifiers import RegimeClassification, classify_robustness_report
from .stress_regimes import evaluate_all_canonical_stress_regimes
from .transition_archetypes import evaluate_all_canonical_transition_archetypes, summarize_transition_archetype
from .types import CGTParameters


@dataclass(frozen=True, slots=True)
class TrajectoryMapPoint:
    regime_id: str
    archetype_id: str
    label: str
    severity: float
    transition_center: float
    compatibility_center: float
    aftermath_center: float


@dataclass(frozen=True, slots=True)
class TrajectoryMap:
    points: tuple[TrajectoryMapPoint, ...]
    dominant_label: str
    archetype_histogram: dict[str, float]
    regime_histogram: dict[str, float]


_LABEL_TO_ARCHETYPE: dict[str, str] = {
    "stable-core": "balanced-bridge",
    "gating-stressed": "recovery-arc",
    "lock-edge": "lock-edge-arc",
    "retention-pressured": "recovery-arc",
}


def _choose_archetype(label: str) -> str:
    return _LABEL_TO_ARCHETYPE.get(label, "balanced-bridge")


def evaluate_regime_trajectory_map(*, base_parameters: CGTParameters) -> TrajectoryMap:
    archetype_evals = {
        archetype.archetype_id: summarize_transition_archetype(archetype, result)
        for archetype, result in evaluate_all_canonical_transition_archetypes(base_parameters=base_parameters)
    }
    stress_reports = evaluate_all_canonical_stress_regimes(base_parameters=base_parameters)

    points: list[TrajectoryMapPoint] = []
    archetype_histogram: dict[str, float] = {}
    regime_histogram: dict[str, float] = {}
    label_histogram: dict[str, float] = {}
    for regime, report in stress_reports:
        classification: RegimeClassification = classify_robustness_report(regime.regime_id, report)
        archetype_id = _choose_archetype(classification.label)
        archetype_summary = archetype_evals[archetype_id]
        points.append(
            TrajectoryMapPoint(
                regime_id=regime.regime_id,
                archetype_id=archetype_id,
                label=classification.label,
                severity=classification.severity,
                transition_center=archetype_summary["transition_center"],
                compatibility_center=archetype_summary["compatibility_center"],
                aftermath_center=archetype_summary["aftermath_center"],
            )
        )
        archetype_histogram[archetype_id] = archetype_histogram.get(archetype_id, 0.0) + 1.0
        regime_histogram[regime.regime_id] = regime_histogram.get(regime.regime_id, 0.0) + 1.0
        label_histogram[classification.label] = label_histogram.get(classification.label, 0.0) + 1.0

    dominant_label = max(label_histogram.items(), key=lambda item: (item[1], item[0]))[0]
    return TrajectoryMap(
        points=tuple(points),
        dominant_label=dominant_label,
        archetype_histogram=archetype_histogram,
        regime_histogram=regime_histogram,
    )


def summarize_trajectory_map(trajectory_map: TrajectoryMap) -> dict[str, float]:
    count = len(trajectory_map.points)
    severities = [point.severity for point in trajectory_map.points]
    transition_centers = [point.transition_center for point in trajectory_map.points]
    compatibility_centers = [point.compatibility_center for point in trajectory_map.points]
    aftermath_centers = [point.aftermath_center for point in trajectory_map.points]
    return {
        "point_count": float(count),
        "mean_severity": math.fsum(severities) / count,
        "mean_transition_center": math.fsum(transition_centers) / count,
        "mean_compatibility_center": math.fsum(compatibility_centers) / count,
        "mean_aftermath_center": math.fsum(aftermath_centers) / count,
        "unique_archetypes": float(len(trajectory_map.archetype_histogram)),
        "unique_regimes": float(len(trajectory_map.regime_histogram)),
    }
