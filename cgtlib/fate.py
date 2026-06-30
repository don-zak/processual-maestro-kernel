from __future__ import annotations

from cgtlib.private import compute as _compute
from cgtlib.types import ExistenceRank, FateVector


def compute_repeatability(retention: float, harmony: float, compatibility: float, distortion: float) -> float:
    from cgtlib.private.equations import repeatability
    return repeatability(retention, harmony, compatibility, distortion)


def compute_hybridity_indicator(transition_channel: float, compatibility: float, diversity: float) -> float:
    from cgtlib.private.equations import hybridity_indicator
    return hybridity_indicator(transition_channel, compatibility, diversity)


def compute_distortion_indicator(hybridity: float, complexity: float, shock: float, harmony: float, eta: float = 1e-6) -> float:
    from cgtlib.private.equations import distortion_indicator
    return distortion_indicator(hybridity, complexity, shock, harmony, eta)


def compute_stability_indicator(repeatability: float, fatigue: float, lift: float = 0.0) -> float:
    from cgtlib.private.equations import stability_indicator
    return stability_indicator(repeatability, fatigue, lift)


def compute_extinction_indicator(compatibility: float, dwell_time: float, carrier: float, **kwargs) -> float:
    from cgtlib.private.equations import extinction_indicator
    from cgtlib.private.thresholds import CARRIER_THRESHOLD, K_ZERO, TAU_MIN
    return extinction_indicator(compatibility, dwell_time, carrier, k_zero=K_ZERO, tau_min=TAU_MIN, carrier_threshold=CARRIER_THRESHOLD)


def compute_collapse_from_fate(distortion: float, fatigue: float, shock: float, harmony: float) -> float:
    from cgtlib.private.equations import collapse_from_fate
    return collapse_from_fate(distortion, fatigue, shock, harmony)


def compute_flourishing_potential(stability: float, repeatability: float, novelty: float, distortion: float) -> float:
    from cgtlib.private.equations import flourishing_potential
    return flourishing_potential(stability, repeatability, novelty, distortion)


def compute_fate_balance(fate: FateVector) -> float:
    return _compute.compute_fate_balance(fate.stability, fate.hybridity, fate.distortion, fate.extinction, fate.collapse, fate.flourishing)


def classify_existence_rank(fate: FateVector) -> ExistenceRank:
    return _compute.classify_existence_rank(fate)


def evaluate_fate_vector(**kwargs) -> FateVector:
    return _compute.evaluate_fate_vector(**kwargs)
