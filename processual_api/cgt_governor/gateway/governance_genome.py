"""Public-safe Maestro Governance Genome v2 candidate.

This deterministic runtime configuration mirrors the qualified engineering
principles from the private qualification work without exposing private
integration logic or artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EvidenceLevel(StrEnum):
    E0_EXPLORATORY = "E0"
    E1_REPLICATED = "E1"
    E2_NULL_QUALIFIED = "E2"
    E3_REPRESENTATION_QUALIFIED = "E3"
    E4_CROSSFIT_QUALIFIED = "E4"
    E5_EXTERNAL_DOMAIN_QUALIFIED = "E5"
    E6_INTERVENTIONAL_COMPOSITIONAL = "E6"
    E7_TEMPORAL_HISTORY_QUALIFIED = "E7"


class GovernanceGate(StrEnum):
    CONSTITUTIVE_CONSTRAINT = "constitutive_constraint"
    AUTHORIZATION = "authorization"
    EVIDENCE = "evidence"
    OPTIMIZATION = "optimization"


@dataclass(frozen=True)
class GovernanceGenomeConfig:
    version: str = "2.0-candidate-public"
    default_fail_closed: bool = True
    constitutive_constraint_threshold: float = 1.0
    authorization_failure_threshold: float = 1.0
    missing_evidence_threshold: float = 1.0
    consecutive_failure_escalation_limit: int = 3
    runtime_claim_ceiling: EvidenceLevel = EvidenceLevel.E4_CROSSFIT_QUALIFIED
    precedence: tuple[GovernanceGate, ...] = (
        GovernanceGate.CONSTITUTIVE_CONSTRAINT,
        GovernanceGate.AUTHORIZATION,
        GovernanceGate.EVIDENCE,
        GovernanceGate.OPTIMIZATION,
    )

    @staticmethod
    def _signal(signals: dict[str, float], key: str) -> float:
        value = signals.get(key, 0.0)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 1.0

    def first_failed_gate(self, risk_signals: dict[str, float] | None) -> GovernanceGate | None:
        signals = risk_signals or {}
        if self._signal(signals, "constraint_failure") >= self.constitutive_constraint_threshold:
            return GovernanceGate.CONSTITUTIVE_CONSTRAINT
        if self._signal(signals, "authorization_failure") >= self.authorization_failure_threshold:
            return GovernanceGate.AUTHORIZATION
        if self._signal(signals, "missing_required_evidence") >= self.missing_evidence_threshold:
            return GovernanceGate.EVIDENCE
        return None


governance_genome = GovernanceGenomeConfig()
