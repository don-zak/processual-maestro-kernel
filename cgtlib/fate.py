from __future__ import annotations

from cgtlib._backend import compute as _compute
from cgtlib._backend import require_private_module
from cgtlib.types import ExistenceRank, FateVector


def compute_repeatability(retention: float, harmony: float, compatibility: float, distortion: float) -> float:
    equations = require_private_module("equations", "compute_repeatability")
    return equations.repeatability(retention, harmony, compatibility, distortion)


def compute_hybridity_indicator(transition_channel: float, compatibility: float, diversity: float) -> float:
    equations = require_private_module("equations", "compute_hybridity_indicator")
    return equations.hybridity_indicator(transition_channel, compatibility, diversity)


def compute_distortion_indicator(
    hybridity: float, complexity: float, shock: float, harmony: float, eta: float = 1e-6
) -> float:
    equations = require_private_module("equations", "compute_distortion_indicator")
    return equations.distortion_indicator(hybridity, complexity, shock, harmony, eta)


def compute_stability_indicator(repeatability: float, fatigue: float, lift: float = 0.0) -> float:
    equations = require_private_module("equations", "compute_stability_indicator")
    return equations.stability_indicator(repeatability, fatigue, lift)


def compute_extinction_indicator(compatibility: float, dwell_time: float, carrier: float, **kwargs) -> float:
    equations = require_private_module("equations", "compute_extinction_indicator")
    thresholds = require_private_module("thresholds", "compute_extinction_indicator")
    return equations.extinction_indicator(
        compatibility,
        dwell_time,
        carrier,
        k_zero=thresholds.K_ZERO,
        tau_min=thresholds.TAU_MIN,
        carrier_threshold=thresholds.CARRIER_THRESHOLD,
    )


def compute_collapse_from_fate(distortion: float, fatigue: float, shock: float, harmony: float) -> float:
    equations = require_private_module("equations", "compute_collapse_from_fate")
    return equations.collapse_from_fate(distortion, fatigue, shock, harmony)


def compute_flourishing_potential(stability: float, repeatability: float, novelty: float, distortion: float) -> float:
    equations = require_private_module("equations", "compute_flourishing_potential")
    return equations.flourishing_potential(stability, repeatability, novelty, distortion)


def compute_fate_balance(fate: FateVector) -> float:
    return _compute.compute_fate_balance(
        fate.stability, fate.hybridity, fate.distortion, fate.extinction, fate.collapse, fate.flourishing
    )


def classify_existence_rank(fate: FateVector) -> ExistenceRank:
    return _compute.classify_existence_rank(fate)


def evaluate_fate_vector(**kwargs) -> FateVector:
    return _compute.evaluate_fate_vector(**kwargs)
