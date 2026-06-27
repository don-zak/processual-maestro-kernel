"""CGT Governor — LLM Output Governance Layer

Usage:
    from processual_api.cgt_governor import govern_answer
    result = govern_answer(answer="...", compatibility=0.68, ...)
"""

from .analyzer import analyze_cgt
from .classifier import classify_rank, decide_policy
from .evaluator import compute_fate_vector, existential_score, maturity_score
from .governor import govern_answer
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
    "analyze_cgt",
]
