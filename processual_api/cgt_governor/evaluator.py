"""CGT Governor — Core Evaluation Functions

Computes existential admissibility, maturity, and the full fate vector
for an LLM-generated answer based on CGT principles.
"""

from __future__ import annotations

from .math_utils import clamp01, sigmoid
from .types import FateVector


def existential_score(
    origin: float,
    carrier: float,
    effect: float,
    threshold: float = 1.1,
) -> float:
    """CGT existential admissibility score.

    A response with no origin, no carrier, and no effect is functionally extinct.
    """
    origin = clamp01(origin)
    carrier = clamp01(carrier)
    effect = clamp01(effect)

    if origin == 0.0 and carrier == 0.0 and effect == 0.0:
        return 0.0

    z = 1.0 * origin + 1.0 * carrier + 1.0 * effect - threshold
    return clamp01(sigmoid(z))


def constrained_possibility(
    raw_potential: float,
    constraint: float,
    carrier: float,
) -> float:
    """Constrained possibility under CGT.

    Possibility becomes operative only through constraint and carrier.
    """
    return clamp01(raw_potential) * clamp01(constraint) * clamp01(carrier)


def maturity_score(
    compatibility: float,
    coherence: float,
    structural_support: float,
    usefulness: float,
    distortion: float,
    overload: float,
    threshold: float = 1.8,
) -> float:
    """Estimate maturity of an LLM output under CGT.

    Maturity is not length — it is structural integrity:
    - understanding the question
    - respecting constraints
    - clear structure
    - distinguishing rule from exception
    - no contradiction
    - applicable and useful
    """
    z = (
        1.2 * clamp01(compatibility)
        + 1.0 * clamp01(coherence)
        + 0.9 * clamp01(structural_support)
        + 0.8 * clamp01(usefulness)
        - 1.1 * clamp01(distortion)
        - 0.6 * clamp01(overload)
        - threshold
    )
    return clamp01(sigmoid(z))


def lift_score(
    corrigibility: float,
    effective_time: float,
    intensity: float,
    carrier: float,
    overload: float = 0.0,
) -> float:
    """CGT lift — an answer's capacity to be improved.

    A hybrid answer with high lift can be repaired into a stable one.
    """
    return (
        clamp01(corrigibility)
        * clamp01(effective_time)
        * clamp01(intensity)
        * clamp01(carrier)
        * (1.0 - clamp01(overload))
    )


def compute_fate_vector(
    *,
    compatibility: float,
    coherence: float,
    structural_support: float,
    usefulness: float,
    complexity: float,
    fatigue: float,
    shock: float,
    lift: float,
    novelty: float,
    no_answer: float,
    hallucination: float,
    constraint_failure: float,
) -> FateVector:
    """Compute a CGT fate vector for an LLM answer.

    Accepts keyword arguments for all evaluation dimensions.
    Returns a FateVector with all seven components: stability, hybridity,
    distortion, extinction, collapse, flourishing, transient.
    """
    compatibility = clamp01(compatibility)
    coherence = clamp01(coherence)
    structural_support = clamp01(structural_support)
    usefulness = clamp01(usefulness)
    complexity = clamp01(complexity)
    fatigue = clamp01(fatigue)
    shock = clamp01(shock)
    lift = clamp01(lift)
    novelty = clamp01(novelty)
    no_answer = clamp01(no_answer)
    hallucination = clamp01(hallucination)
    constraint_failure = clamp01(constraint_failure)

    # Extinction: failure modes
    extinction = clamp01(
        0.45 * no_answer + 0.35 * hallucination + 0.35 * constraint_failure + 0.20 * (1.0 - compatibility)
    )

    # Preliminary distortion for stability calculation
    preliminary_distortion = clamp01(complexity * (1.0 - coherence + shock) / 2.0)

    # Stability: structural integrity
    core = (compatibility * coherence * structural_support * usefulness) ** 0.25
    stability = clamp01(core * (1.0 - preliminary_distortion) * (1.0 - fatigue))

    # Hybridity: useful core but incomplete
    core_h = (compatibility * (1.0 - compatibility) * structural_support * usefulness) ** 0.25
    hybridity = clamp01(core_h * (0.5 + 0.5 * lift))

    # Distortion: excessive complexity without coherence
    distortion = clamp01(hybridity * (complexity + shock + fatigue) / (coherence + 0.15))

    # Collapse: structural breakdown
    collapse = clamp01(0.50 * distortion + 0.30 * fatigue + 0.30 * shock - 0.30 * coherence)

    # Flourishing: stable + useful + novel + undistorted
    core_f = (stability * usefulness * novelty) ** (1 / 3)
    flourishing = clamp01(core_f * (1.0 - distortion))

    # Transient: useful but lacks support, not quite extinct
    transient = clamp01(usefulness * (1.0 - structural_support) * (1.0 - stability) * (1.0 - extinction))

    return FateVector(
        stability=stability,
        hybridity=hybridity,
        distortion=distortion,
        extinction=extinction,
        collapse=collapse,
        flourishing=flourishing,
        transient=transient,
    )
