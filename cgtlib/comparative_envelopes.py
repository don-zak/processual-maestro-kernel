from __future__ import annotations

import math
from dataclasses import dataclass

from .robustness import RobustnessReport, summarize_robustness_report
from .robustness_profiles import RobustnessProfile, evaluate_all_canonical_robustness_profiles
from .scenarios import ScenarioPack
from .types import CGTParameters
from .validation import ensure_not_empty


@dataclass(frozen=True, slots=True)
class ComparativeEnvelope:
    profile_id: str
    summary: dict[str, float]
    axis_count: int
    grid_size: int


@dataclass(frozen=True, slots=True)
class ComparativeEnvelopeReport:
    envelopes: tuple[ComparativeEnvelope, ...]
    metric_envelopes: dict[str, tuple[float, float]]


_METRICS = (
    "max_transition_span",
    "mean_transition_channel_span",
    "mean_compatibility_span",
    "mean_aftermath_balance_span",
    "max_surface_transition_span",
    "max_surface_compatibility_span",
    "max_surface_aftermath_balance_span",
)


def _to_envelope(profile: RobustnessProfile, report: RobustnessReport) -> ComparativeEnvelope:
    summary = summarize_robustness_report(report)
    return ComparativeEnvelope(
        profile_id=profile.profile_id,
        summary=summary,
        axis_count=len(report.axis_names),
        grid_size=len(report.parameter_grid),
    )


def evaluate_comparative_envelopes(
    packs: list[ScenarioPack],
    *,
    base_parameters: CGTParameters,
) -> ComparativeEnvelopeReport:
    profile_reports = evaluate_all_canonical_robustness_profiles(
        packs,
        base_parameters=base_parameters,
    )
    envelopes = tuple(_to_envelope(profile, report) for profile, report in profile_reports)
    ensure_not_empty(envelopes, "envelopes")

    metric_envelopes: dict[str, tuple[float, float]] = {}
    for metric in _METRICS:
        values = [envelope.summary[metric] for envelope in envelopes]
        metric_envelopes[metric] = (min(values), max(values))
    return ComparativeEnvelopeReport(
        envelopes=envelopes,
        metric_envelopes=metric_envelopes,
    )


def summarize_comparative_envelopes(report: ComparativeEnvelopeReport) -> dict[str, float]:
    ensure_not_empty(report.envelopes, "report.envelopes")
    profile_count = len(report.envelopes)
    grid_sizes = [float(envelope.grid_size) for envelope in report.envelopes]
    axis_counts = [float(envelope.axis_count) for envelope in report.envelopes]

    summary: dict[str, float] = {
        "profile_count": float(profile_count),
        "mean_grid_size": math.fsum(grid_sizes) / profile_count,
        "mean_axis_count": math.fsum(axis_counts) / profile_count,
    }
    for metric, bounds in report.metric_envelopes.items():
        lower, upper = bounds
        summary[f"{metric}_min"] = lower
        summary[f"{metric}_max"] = upper
        summary[f"{metric}_span"] = upper - lower
    return summary
