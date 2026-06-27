from __future__ import annotations

import math
from dataclasses import dataclass

from .catalogs import build_all_canonical_scenario_packs
from .comparative_envelopes import (
    ComparativeEnvelopeReport,
    evaluate_comparative_envelopes,
    summarize_comparative_envelopes,
)
from .robustness import RobustnessReport, summarize_robustness_report
from .stress_regimes import evaluate_all_canonical_stress_regimes
from .types import CGTParameters


@dataclass(frozen=True, slots=True)
class RegimeClassification:
    subject_id: str
    label: str
    severity: float
    evidence: dict[str, float]


@dataclass(frozen=True, slots=True)
class RegimeClassifierReport:
    classifications: tuple[RegimeClassification, ...]
    dominant_label: str
    label_histogram: dict[str, float]
    mean_severity: float
    comparative_summary: dict[str, float]


def _label_from_summary(summary: dict[str, float]) -> tuple[str, float]:
    transition_span = summary.get("max_transition_span", summary.get("max_transition_span_max", 0.0))
    gating_span = summary.get("max_surface_transition_span", summary.get("max_surface_transition_span_max", 0.0))
    compatibility_span = summary.get(
        "max_surface_compatibility_span", summary.get("max_surface_compatibility_span_max", 0.0)
    )
    aftermath_span = summary.get(
        "max_surface_aftermath_balance_span", summary.get("max_surface_aftermath_balance_span_max", 0.0)
    )

    severity = max(transition_span, gating_span, compatibility_span, min(1.0, aftermath_span / 2.0))
    if transition_span >= 0.3 or aftermath_span >= 0.7:
        return "retention-pressured", severity
    if gating_span >= 0.18:
        return "gating-stressed", severity
    if compatibility_span >= 0.12:
        return "lock-edge", severity
    return "stable-core", severity


def classify_robustness_report(subject_id: str, report: RobustnessReport) -> RegimeClassification:
    summary = summarize_robustness_report(report)
    label, severity = _label_from_summary(summary)
    evidence = {
        "max_transition_span": summary["max_transition_span"],
        "max_surface_transition_span": summary["max_surface_transition_span"],
        "max_surface_compatibility_span": summary["max_surface_compatibility_span"],
        "max_surface_aftermath_balance_span": summary["max_surface_aftermath_balance_span"],
    }
    return RegimeClassification(
        subject_id=subject_id,
        label=label,
        severity=severity,
        evidence=evidence,
    )


def classify_comparative_envelopes(report: ComparativeEnvelopeReport) -> RegimeClassification:
    summary = summarize_comparative_envelopes(report)
    label, severity = _label_from_summary(summary)
    evidence = {
        "max_transition_span_max": summary["max_transition_span_max"],
        "max_surface_transition_span_max": summary["max_surface_transition_span_max"],
        "max_surface_compatibility_span_max": summary["max_surface_compatibility_span_max"],
        "max_surface_aftermath_balance_span_max": summary["max_surface_aftermath_balance_span_max"],
    }
    return RegimeClassification(
        subject_id="comparative_envelopes",
        label=label,
        severity=severity,
        evidence=evidence,
    )


def evaluate_canonical_regime_classifier_report(*, base_parameters: CGTParameters) -> RegimeClassifierReport:
    profile_report = evaluate_comparative_envelopes(
        list(build_all_canonical_scenario_packs()),
        base_parameters=base_parameters,
    )
    comparative_summary = summarize_comparative_envelopes(profile_report)
    stress_reports = evaluate_all_canonical_stress_regimes(base_parameters=base_parameters)
    classifications = [classify_robustness_report(regime.regime_id, report) for regime, report in stress_reports]
    classifications.append(classify_comparative_envelopes(profile_report))

    histogram: dict[str, float] = {}
    for classification in classifications:
        histogram[classification.label] = histogram.get(classification.label, 0.0) + 1.0
    dominant_label = max(histogram.items(), key=lambda item: (item[1], item[0]))[0]
    mean_severity = math.fsum(item.severity for item in classifications) / len(classifications)
    return RegimeClassifierReport(
        classifications=tuple(classifications),
        dominant_label=dominant_label,
        label_histogram=histogram,
        mean_severity=mean_severity,
        comparative_summary=comparative_summary,
    )
