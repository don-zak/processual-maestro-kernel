from __future__ import annotations

from cgtlib._fallback import (
    _FeatureUnavailableError,
    classify_existence_rank as _classify_existence_rank,
    compute_distortion_indicator as _compute_distortion_indicator,
    compute_extinction_indicator as _compute_extinction_indicator,
    compute_fate_balance as _compute_fate_balance,
    compute_flourishing_potential as _compute_flourishing_potential,
    compute_hybridity_indicator as _compute_hybridity_indicator,
    compute_repeatability as _compute_repeatability,
    compute_stability_indicator as _compute_stability_indicator,
    evaluate_fate_vector as _evaluate_fate_vector,
)
from cgtlib.types import ExistenceRank, FateVector


def compute_repeatability(retention: float, harmony: float, compatibility: float, distortion: float) -> float:
    return _compute_repeatability(retention, harmony, compatibility, distortion)


def compute_hybridity_indicator(transition_channel: float, compatibility: float, diversity: float) -> float:
    return _compute_hybridity_indicator(transition_channel, compatibility, diversity)


def compute_distortion_indicator(
    hybridity: float,
    complexity: float,
    shock: float,
    harmony: float,
    eta: float = 1e-6,
) -> float:
    return _compute_distortion_indicator(hybridity, complexity, shock, harmony, eta)


def compute_stability_indicator(repeatability: float, fatigue: float, lift: float = 0.0) -> float:
    return _compute_stability_indicator(repeatability, fatigue, lift)


def compute_extinction_indicator(
    compatibility: float,
    dwell_time: float,
    carrier: float,
    **kwargs: object,
) -> float:
    return _compute_extinction_indicator(compatibility, dwell_time, carrier, **kwargs)


def compute_collapse_from_fate(
    distortion: float,
    fatigue: float,
    shock: float,
    harmony: float,
) -> float:
    raise _FeatureUnavailableError("compute_collapse_from_fate")


def compute_flourishing_potential(
    stability: float,
    repeatability: float,
    novelty: float,
    distortion: float,
) -> float:
    return _compute_flourishing_potential(stability, repeatability, novelty, distortion)


def compute_fate_balance(fate: FateVector) -> float:
    return _compute_fate_balance(fate)


def classify_existence_rank(fate: FateVector) -> ExistenceRank:
    return _classify_existence_rank(fate)


def evaluate_fate_vector(**kwargs: object) -> FateVector:
    return _evaluate_fate_vector(**kwargs)
