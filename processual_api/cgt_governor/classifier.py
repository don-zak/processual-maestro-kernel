"""CGT Governor — Rank Classification and Policy Decision"""

from __future__ import annotations

from .types import GOVERNANCE_POLICIES, ExistenceRank, FateVector


def classify_rank(fate: FateVector) -> ExistenceRank:
    """Classify answer fate into a CGT existence rank.

    Priority order:
    1. Extinct (fails to carry meaning)
    2. Flourishing (opens new understanding)
    3. Stable (consistent and reliable)
    4. Distorted (over-structured, confused)
    5. Hybrid (useful core, incomplete)
    6. Transient (fallback: superficial)
    """
    if fate.extinction >= 0.75:
        return ExistenceRank.EXTINCT

    if fate.flourishing >= 0.65:
        return ExistenceRank.FLOURISHING

    if fate.stability >= 0.60:
        return ExistenceRank.STABLE

    if fate.distortion >= 0.55:
        return ExistenceRank.DISTORTED

    if fate.hybridity >= 0.45:
        return ExistenceRank.HYBRID

    return ExistenceRank.TRANSIENT


def decide_policy(rank: ExistenceRank) -> str:
    """Map a CGT existence rank to a governance action string."""
    entry = GOVERNANCE_POLICIES.get(rank)
    if entry is None:
        raise ValueError(f"Unsupported rank: {rank}")
    return entry["action"]


def policy_info(action: str) -> dict:
    """Look up policy metadata by action name."""
    for rank, entry in GOVERNANCE_POLICIES.items():
        if entry["action"] == action:
            return {**entry, "rank": rank.value}
    return {"action": action, "label": action, "description": "", "emoji": ""}
