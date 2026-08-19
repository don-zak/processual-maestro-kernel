"""Public CGT governance orchestration over sanitized private decisions.

This module intentionally performs no proprietary mathematical evaluation.
The private execution environment owns all protected scoring, ranking math,
thresholds, weights, calibration, and intermediate state. Public governance
may only consume the bounded decision contract exposed by the trust boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from processual_api.integrations.private_evaluation_boundary import (
    PrivateEvaluationUnavailableError,
    SanitizedPrivateDecision,
)

from .classifier import decide_policy, policy_info
from .repair import (
    build_distortion_repair_prompt,
    build_hybrid_repair_prompt,
    build_transient_deepen_prompt,
)
from .types import ExistenceRank


@dataclass(frozen=True, slots=True)
class SanitizedGovernedAnswer:
    """Public governance result with no private mathematical intermediates."""

    rank: ExistenceRank
    policy: str
    policy_label: str
    policy_description: str
    dominant_constraint: str
    next_gate: str
    confidence_band: str
    explanation_code: str
    policy_version: str
    repair_prompt: str | None = None


def _repair_prompt_for_policy(answer: str, policy: str, language: str) -> str | None:
    if policy == "repair_scaffold":
        return build_hybrid_repair_prompt(answer, language=language)
    if policy == "restructure":
        return build_distortion_repair_prompt(answer, language=language)
    if policy == "deepen_or_clarify":
        return build_transient_deepen_prompt(answer, language=language)
    return None


def govern_sanitized_decision(
    answer: str,
    decision: SanitizedPrivateDecision,
    *,
    language: str = "en",
) -> SanitizedGovernedAnswer:
    """Apply public policy and repair orchestration to a sanitized private decision."""

    try:
        rank = ExistenceRank(decision.existence_rank.removeprefix("rank:" ).lower())
    except ValueError as exc:
        raise ValueError("unsupported_sanitized_existence_rank") from exc

    policy = decide_policy(rank)
    info = policy_info(policy)
    return SanitizedGovernedAnswer(
        rank=rank,
        policy=policy,
        policy_label=info.get("label", policy),
        policy_description=info.get("description", ""),
        dominant_constraint=decision.dominant_constraint,
        next_gate=decision.next_gate,
        confidence_band=decision.confidence_band,
        explanation_code=decision.explanation_code,
        policy_version=decision.policy_version,
        repair_prompt=_repair_prompt_for_policy(answer, policy, language),
    )


def govern_answer(*args: object, **kwargs: object) -> SanitizedGovernedAnswer:
    """Legacy entrypoint retained fail-closed for callers not using the boundary.

    The previous implementation performed protected mathematical evaluation in
    the public runtime. That behavior is intentionally disabled. Callers must
    obtain a ``SanitizedPrivateDecision`` through the controlled private
    evaluation boundary and then call ``govern_sanitized_decision``.
    """

    del args, kwargs
    raise PrivateEvaluationUnavailableError("private_evaluation_unavailable")
