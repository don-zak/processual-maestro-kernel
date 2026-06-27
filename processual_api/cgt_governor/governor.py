"""CGT Governor — Orchestrator

The main `govern_answer()` function that:
1. Computes maturity, premature risk, and mature speed
2. Computes the full CGT fate vector
3. Computes the variable reinforcement reward
4. Classifies the existence rank
5. Decides the governance policy
6. Builds a repair prompt if applicable

Returns a `GovernedAnswer` dataclass with all results.
"""

from __future__ import annotations

from .classifier import classify_rank, decide_policy, policy_info
from .evaluator import compute_fate_vector, maturity_score
from .repair import (
    build_distortion_repair_prompt,
    build_hybrid_repair_prompt,
    build_transient_deepen_prompt,
)
from .reward import cgt_reward, mature_speed_value, premature_speed_risk
from .types import GovernedAnswer


def govern_answer(
    answer: str,
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
    speed: float = 0.5,
    language: str = "en",
) -> GovernedAnswer:
    """Govern an LLM answer through the full CGT pipeline.

    All numeric parameters must be in [0, 1] range.

    Args:
        answer: The LLM-generated text to evaluate.
        compatibility: How well the answer matches the query intent.
        coherence: Internal consistency and clarity.
        structural_support: Whether the answer has clear structure.
        usefulness: Practical value to the user.
        complexity: Structural complexity pressure.
        fatigue: System wear coefficient.
        shock: External shock magnitude.
        lift: Answer's corrigibility / capacity for improvement.
        novelty: New understanding or path opened.
        no_answer: Degree to which the answer fails to address the query.
        hallucination: Degree of hallucinated or fabricated content.
        constraint_failure: Degree of constraint / safety boundary violation.
        speed: How quickly the answer was produced.
        language: "en" for English repair prompts, "ar" for Arabic.

    Returns:
        GovernedAnswer with fate vector, rank, reward, policy, and repair prompt.
    """
    # 1. Maturity
    distortion_estimate = complexity * (1.0 - coherence)
    maturity = maturity_score(
        compatibility=compatibility,
        coherence=coherence,
        structural_support=structural_support,
        usefulness=usefulness,
        distortion=distortion_estimate,
        overload=complexity,
    )

    # 2. Speed components
    premature = premature_speed_risk(
        speed=speed,
        maturity=maturity,
        compatibility=compatibility,
        coherence=coherence,
    )

    mature_spd = mature_speed_value(
        speed=speed,
        maturity=maturity,
        compatibility=compatibility,
        coherence=coherence,
    )

    # 3. Fate vector
    fate = compute_fate_vector(
        compatibility=compatibility,
        coherence=coherence,
        structural_support=structural_support,
        usefulness=usefulness,
        complexity=complexity,
        fatigue=fatigue,
        shock=shock,
        lift=lift,
        novelty=novelty,
        no_answer=no_answer,
        hallucination=hallucination,
        constraint_failure=constraint_failure,
    )

    # 4. Reward
    reward = cgt_reward(
        fate=fate,
        lift=lift,
        mature_speed=mature_spd,
        premature_risk=premature,
    )

    # 5. Classification
    rank = classify_rank(fate)

    # 6. Policy
    policy = decide_policy(rank)
    pinfo = policy_info(policy)

    # 7. Repair prompt
    repair_prompt = None
    if policy == "repair_scaffold":
        repair_prompt = build_hybrid_repair_prompt(answer, language=language)
    elif policy == "restructure":
        repair_prompt = build_distortion_repair_prompt(answer, language=language)
    elif policy == "deepen_or_clarify":
        repair_prompt = build_transient_deepen_prompt(answer, language=language)

    return GovernedAnswer(
        answer=answer,
        fate=fate,
        rank=rank,
        reward=round(reward, 4),
        policy=policy,
        policy_label=pinfo.get("label", policy),
        policy_description=pinfo.get("description", ""),
        repair_prompt=repair_prompt,
    )
