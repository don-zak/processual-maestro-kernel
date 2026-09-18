"""Dynamic qualification layer above public CGT governance outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .sufficiency import SufficiencyStatus, TaskSufficiencyEvidence
from .verification import VerificationEvidence, VerificationStatus


class QualificationState(StrEnum):
    QUALIFIED = "qualified"
    CONDITIONAL = "conditionally_qualified"
    DISQUALIFIED = "disqualified"


class TrajectoryState(StrEnum):
    INSUFFICIENT_DATA = "insufficient_data"
    IMPROVING = "improving"
    STABLE = "stable"
    WORSENING = "worsening"


class QualificationAction(StrEnum):
    ALLOW = "allow"
    REPAIR = "repair"
    VERIFY = "verify"
    BLOCK = "block"


@dataclass(frozen=True)
class QualificationEnvelope:
    state: QualificationState
    distance_to_viability: float
    trajectory: TrajectoryState
    recommended_action: QualificationAction
    required_evidence: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    components: dict[str, str] = field(default_factory=dict)
    component_risks: dict[str, float] = field(default_factory=dict)
    feedback_signals: dict[str, float] = field(default_factory=dict)

    def as_policy_signals(self) -> dict[str, float]:
        return dict(self.feedback_signals)

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "distance_to_viability": self.distance_to_viability,
            "trajectory": self.trajectory.value,
            "recommended_action": self.recommended_action.value,
            "required_evidence": list(self.required_evidence),
            "reasons": list(self.reasons),
            "components": dict(self.components),
            "component_risks": dict(self.component_risks),
            "feedback_signals": dict(self.feedback_signals),
        }


class DynamicQualificationLayer:
    _STRUCTURAL_RISK = {
        "flourishing": 0.0,
        "stable": 0.10,
        "hybrid": 0.45,
        "transient": 0.55,
        "distorted": 0.85,
        "extinct": 1.0,
    }
    _VERIFICATION_RISK = {
        VerificationStatus.NOT_REQUIRED: 0.0,
        VerificationStatus.VERIFIED: 0.0,
        VerificationStatus.UNVERIFIED: 0.65,
        VerificationStatus.CONTRADICTED: 1.0,
    }
    _SUFFICIENCY_RISK = {
        SufficiencyStatus.NOT_REQUIRED: 0.0,
        SufficiencyStatus.SUFFICIENT: 0.0,
        SufficiencyStatus.UNVERIFIED: 0.65,
        SufficiencyStatus.INSUFFICIENT: 1.0,
    }

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @classmethod
    def qualify(
        cls,
        *,
        rank: str,
        risk_signals: dict[str, float] | None = None,
        verification: VerificationEvidence | None = None,
        sufficiency: TaskSufficiencyEvidence | None = None,
        previous_distance: float | None = None,
        previous_component_risks: dict[str, float] | None = None,
    ) -> QualificationEnvelope:
        signals = risk_signals or {}
        evidence = verification or VerificationEvidence()
        suff = sufficiency or TaskSufficiencyEvidence()

        structural = cls._STRUCTURAL_RISK.get(rank, 0.75)
        factual = cls._VERIFICATION_RISK[evidence.factual]
        execution = cls._VERIFICATION_RISK[evidence.execution]
        sufficiency_risk = cls._SUFFICIENCY_RISK[suff.status]
        constraint = cls._clamp01(signals.get("constraint_failure", 0.0))
        component_risks = {
            "structural": round(structural, 6),
            "factual": round(factual, 6),
            "execution": round(execution, 6),
            "sufficiency": round(sufficiency_risk, 6),
            "constraint": round(constraint, 6),
        }
        distance = cls._clamp01(
            0.40 * structural
            + 0.25 * factual
            + 0.25 * execution
            + 0.10 * constraint
            + 0.15 * sufficiency_risk
        )

        required: list[str] = []
        reasons: list[str] = []
        if evidence.factual == VerificationStatus.UNVERIFIED:
            required.append("factual_verification")
        elif evidence.factual == VerificationStatus.CONTRADICTED:
            reasons.append("factual evidence contradicts the answer")
        if evidence.execution == VerificationStatus.UNVERIFIED:
            required.append("execution_attestation")
        elif evidence.execution == VerificationStatus.CONTRADICTED:
            reasons.append("execution evidence contradicts the claimed action")
        if suff.status == SufficiencyStatus.UNVERIFIED:
            required.append("task_sufficiency_verification")
        elif suff.status == SufficiencyStatus.INSUFFICIENT:
            reasons.append("response does not sufficiently cover the requested task")

        contradicted = (
            evidence.factual == VerificationStatus.CONTRADICTED
            or evidence.execution == VerificationStatus.CONTRADICTED
        )
        unverified = (
            evidence.factual == VerificationStatus.UNVERIFIED
            or evidence.execution == VerificationStatus.UNVERIFIED
            or suff.status == SufficiencyStatus.UNVERIFIED
        )
        if contradicted or suff.status == SufficiencyStatus.INSUFFICIENT or rank in {"extinct", "distorted"}:
            state = QualificationState.DISQUALIFIED
            action = QualificationAction.BLOCK
        elif unverified:
            state = QualificationState.CONDITIONAL
            action = QualificationAction.VERIFY
        elif rank in {"hybrid", "transient"}:
            state = QualificationState.CONDITIONAL
            action = QualificationAction.REPAIR
        else:
            state = QualificationState.QUALIFIED
            action = QualificationAction.ALLOW

        if previous_distance is None:
            trajectory = TrajectoryState.INSUFFICIENT_DATA
        else:
            delta = distance - cls._clamp01(previous_distance)
            if delta < -0.03:
                trajectory = TrajectoryState.IMPROVING
            elif delta > 0.03:
                trajectory = TrajectoryState.WORSENING
            else:
                trajectory = TrajectoryState.STABLE

        feedback = evidence.as_risk_signals()
        feedback.update(suff.as_risk_signals())
        feedback["qualification_distance"] = round(distance, 6)
        if trajectory == TrajectoryState.WORSENING:
            feedback["qualification_worsening"] = 1.0

        previous_risks = previous_component_risks or {}
        for component, current in component_risks.items():
            previous = previous_risks.get(component)
            if previous is None:
                continue
            delta = current - cls._clamp01(previous)
            if delta > 0.03:
                feedback[f"{component}_worsening"] = 1.0
            elif delta < -0.03:
                feedback[f"{component}_improving"] = 1.0

        return QualificationEnvelope(
            state=state,
            distance_to_viability=round(distance, 6),
            trajectory=trajectory,
            recommended_action=action,
            required_evidence=tuple(required),
            reasons=tuple(reasons),
            components={
                "structural": rank,
                "factual": evidence.factual.value,
                "execution": evidence.execution.value,
                "sufficiency": suff.status.value,
                "constraint": "violated" if constraint > 0.0 else "clear",
            },
            component_risks=component_risks,
            feedback_signals=feedback,
        )


qualification_layer = DynamicQualificationLayer()
