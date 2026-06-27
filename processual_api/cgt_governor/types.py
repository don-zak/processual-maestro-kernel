"""CGT Governor - Core Types

Defines ExistenceRank enum, FateVector / CGTState / GovernedAnswer
dataclasses, and the GOVERNANCE_POLICIES registry that maps each
existence rank to a governance action, label, description, and emoji.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExistenceRank(StrEnum):
    FLOURISHING = "flourishing"
    STABLE = "stable"
    HYBRID = "hybrid"
    DISTORTED = "distorted"
    TRANSIENT = "transient"
    EXTINCT = "extinct"


@dataclass(frozen=True)
class FateVector:
    stability: float
    hybridity: float
    distortion: float
    extinction: float
    collapse: float
    flourishing: float
    transient: float = 0.0


@dataclass(frozen=True)
class CGTState:
    origin: float
    carrier: float
    effect: float
    constraint: float
    compatibility: float
    coherence: float
    retention: float
    fatigue: float
    complexity: float
    maturity: float
    speed: float
    lift: float
    shock: float = 0.0


GOVERNANCE_POLICIES = {
    ExistenceRank.FLOURISHING: {
        "action": "accept_expand",
        "label": "Flourishing - Accept & Expand",
        "description": "Accept the answer and optionally add extra value or an additional path.",
        "emoji": "*",
    },
    ExistenceRank.STABLE: {
        "action": "accept",
        "label": "Stable - Accept",
        "description": "Accept the answer as-is. It is consistent and reliable.",
        "emoji": "[OK]",
    },
    ExistenceRank.HYBRID: {
        "action": "repair_scaffold",
        "label": "Hybrid - Repair & Scaffold",
        "description": "Preserve the useful core, remove confusion, and restructure into a stable form.",
        "emoji": "[REPAIR]",
    },
    ExistenceRank.DISTORTED: {
        "action": "restructure",
        "label": "Distorted - Restructure",
        "description": "Rebuild from a new plan. Remove excess branching and conceptual mixing.",
        "emoji": "-",
    },
    ExistenceRank.TRANSIENT: {
        "action": "deepen_or_clarify",
        "label": "Transient - Deepen or Clarify",
        "description": "Add depth, explanation, or ask the user for more context.",
        "emoji": "[DOWN]",
    },
    ExistenceRank.EXTINCT: {
        "action": "reject_regenerate",
        "label": "Extinct - Reject & Regenerate",
        "description": "Fails to carry the required meaning. Regenerate or use a verification tool.",
        "emoji": "[X]",
    },
}

POLICY_ACTIONS = {v["action"]: k for k, v in GOVERNANCE_POLICIES.items()}


@dataclass
class GovernedAnswer:
    answer: str
    fate: FateVector
    rank: ExistenceRank
    reward: float
    policy: str
    policy_label: str = ""
    policy_description: str = ""
    repair_prompt: str | None = None

