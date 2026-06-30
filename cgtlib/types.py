from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class CGTParameters:
    lam: float = 1.0
    omega: float = 1.0
    mu: float = 1.0
    lock_threshold: float = 0.7
    lock_gate_max: float = 0.2
    logistic_k: float = 10.0


@dataclass(frozen=True, slots=True)
class GateState:
    openness: float
    continuity: float | None = None
    transition: float | None = None


@dataclass(frozen=True, slots=True)
class NodeState:
    carrying_capacity: float
    fatigue: float
    local_safety: float
    transmissibility: float | None = None
    retention: float | None = None


@dataclass(frozen=True, slots=True)
class PhaseState:
    phase_id: str
    mass: float
    mean_retention: float
    harmony: float
    fatigue: float
    self_potential: float | None = None


@dataclass(frozen=True, slots=True)
class LockState:
    locked: bool
    self_potential: float
    transition_gate: float
    lock_threshold: float
    lock_gate_max: float


@dataclass(frozen=True, slots=True)
class CompatibilityState:
    source_phase: str
    target_phase: str
    score: float


class ExistenceRank(StrEnum):
    """Ordered CGT existence ranks, from generative flourishing down to extinction."""

    FLOURISHING = "flourishing"
    STABLE = "stable"
    HYBRID = "hybrid"
    DISTORTED = "distorted"
    TRANSIENT = "transient"
    EXTINCT = "extinct"


@dataclass(frozen=True, slots=True)
class ExistenceState:
    origin: float
    carrier: float
    effect: float
    score: float


@dataclass(frozen=True, slots=True)
class PossibilityState:
    raw_potential: float
    constraint: float
    carrier: float
    score: float


@dataclass(frozen=True, slots=True)
class DynamicLiftState:
    dwell_time: float
    pressure: float
    carrier: float
    overload: float
    lift: float


@dataclass(frozen=True, slots=True)
class FateVector:
    stability: float
    hybridity: float
    distortion: float
    extinction: float
    collapse: float
    flourishing: float
    balance: float


@dataclass(frozen=True, slots=True)
class AftermathState:
    collapse_score: float
    flourishing_score: float
    balance: float


@dataclass(frozen=True, slots=True)
class StructuralTransitionReport:
    transmissibility: float
    retention: float
    self_potential: float
    lock_state: LockState
    delay_gate: float
    compatibility: float
    transition_channel: float
    aftermath: AftermathState
    existence: ExistenceState | None = None
    possibility: PossibilityState | None = None
    fate_vector: FateVector | None = None
    existence_rank: ExistenceRank | None = None
    dynamic_lift: DynamicLiftState | None = None
