"""CGT Governor — Variable Reinforcement (Reward) Functions

Computes the CGT variable reinforcement value for an LLM answer,
and its components: premature speed risk and mature speed value.
"""

from __future__ import annotations

from .math_utils import clamp01
from .types import FateVector


def premature_speed_risk(
    speed: float,
    maturity: float,
    compatibility: float,
    coherence: float,
) -> float:
    """High when the answer is fast before reaching maturity.

    CGT rule: speed without maturity, compatibility, and coherence is risky.
    """
    return clamp01(speed) * (1.0 - clamp01(maturity)) * (1.0 - clamp01(compatibility)) * (1.0 - clamp01(coherence))


def mature_speed_value(
    speed: float,
    maturity: float,
    compatibility: float,
    coherence: float,
) -> float:
    """High when speed is produced by a mature, stable structure.

    Fast answers from mature systems are efficient, not risky.
    """
    return clamp01(speed) * clamp01(maturity) * clamp01(compatibility) * clamp01(coherence)


def cgt_reward(
    fate: FateVector,
    lift: float,
    mature_speed: float,
    premature_risk: float,
) -> float:
    """Compute the CGT variable reinforcement value.

    The reward is a weighted sum of fate vector components:
    - Positive weights for flourishing, stability, hybrid-with-lift, mature speed
    - Negative weights for distortion, extinction, collapse, transient, premature speed

    Range: approximately [-1.5, 2.0] in practice.
    """
    return (
        +1.4 * fate.flourishing
        + 1.0 * fate.stability
        + 0.6 * fate.hybridity * clamp01(lift)
        - 0.9 * fate.distortion
        - 1.2 * fate.extinction
        - 1.0 * fate.collapse
        - 0.4 * fate.transient
        + 0.5 * clamp01(mature_speed)
        - 0.8 * clamp01(premature_risk)
    )
