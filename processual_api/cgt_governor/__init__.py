"""CGT Governor public governance layer.

Protected mathematical evaluation is not executed by this package. Runtime
callers must obtain a sanitized private decision through the controlled trust
boundary and apply public policy through ``govern_sanitized_decision``.
"""

from .analyzer import analyze_cgt
from .classifier import classify_rank, decide_policy
from .evaluator import compute_fate_vector, existential_score, maturity_score
from .governor import SanitizedGovernedAnswer, govern_answer, govern_sanitized_decision
from .policy import GovernanceAction, PolicyDecision, PolicyEngine, policy_engine
from .repair import (
    build_distortion_repair_prompt,
    build_hybrid_repair_prompt,
    build_transient_deepen_prompt,
)
from .reward import cgt_reward, mature_speed_value, premature_speed_risk
from .types import CGTState, ExistenceRank, FateVector, GovernedAnswer

__all__ = [
    "ExistenceRank",
    "FateVector",
    "CGTState",
    "GovernedAnswer",
    "SanitizedGovernedAnswer",
    "GovernanceAction",
    "PolicyDecision",
    "PolicyEngine",
    "policy_engine",
    "compute_fate_vector",
    "existential_score",
    "maturity_score",
    "cgt_reward",
    "premature_speed_risk",
    "mature_speed_value",
    "classify_rank",
    "decide_policy",
    "build_hybrid_repair_prompt",
    "build_distortion_repair_prompt",
    "build_transient_deepen_prompt",
    "govern_answer",
    "govern_sanitized_decision",
    "analyze_cgt",
]
