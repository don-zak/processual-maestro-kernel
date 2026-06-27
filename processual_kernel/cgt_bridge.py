from __future__ import annotations

from dataclasses import asdict
from typing import Any

from cgtlib import CGTParameters, PhaseState, StructuralTransitionReport, evaluate_structural_transition

from .continuity import ContinuityEngine, clamp
from .types import Coefficients


class CGTBridge:
    """Adapter from Processual AI coefficients to cgtlib structural transition reports.

    It can evaluate agents, handoff edges, or whole workflows because all three are represented as
    processual entities with T/N/C/M and Ψ.
    """

    def __init__(self, params: CGTParameters | None = None):
        self.params = params or CGTParameters()

    def coefficients_to_phase(self, phase_id: str, coeff: Coefficients, psi: float) -> PhaseState:
        mean_retention = clamp((coeff.T * coeff.N) * (1.0 - 0.5 * coeff.M))
        harmony = clamp(coeff.T * (1.0 - coeff.C))
        fatigue = clamp(0.5 * coeff.C + 0.5 * coeff.M)
        mass = clamp(coeff.N)
        self_potential = ContinuityEngine.normalize_psi(psi)
        return PhaseState(
            phase_id=phase_id,
            mass=mass,
            mean_retention=mean_retention,
            harmony=harmony,
            fatigue=fatigue,
            self_potential=self_potential,
        )

    def feature_vector(self, coeff: Coefficients, psi: float, dpsi: float) -> dict[str, float]:
        return {
            "synergy": clamp(coeff.T),
            "need": clamp(coeff.N),
            "cost_inverse": clamp(1.0 - coeff.C),
            "mortality_inverse": clamp(1.0 - coeff.M),
            "psi": ContinuityEngine.normalize_psi(psi),
            "dpsi_positive": clamp(max(0.0, dpsi)),
            "transition_gate": clamp(max(0.0, -dpsi) + 0.35 * coeff.M + 0.25 * coeff.C),
        }

    def evaluate_transition(
        self,
        entity_id: str,
        previous_coeff: Coefficients,
        current_coeff: Coefficients,
        previous_psi: float,
        current_psi: float,
        dpsi: float,
        fatigue_counter: int = 0,
    ) -> StructuralTransitionReport:
        source = self.coefficients_to_phase(f"{entity_id}@previous", previous_coeff, previous_psi)
        target = self.coefficients_to_phase(f"{entity_id}@current", current_coeff, current_psi)
        source_features = self.feature_vector(previous_coeff, previous_psi, dpsi=0.0)
        target_features = self.feature_vector(current_coeff, current_psi, dpsi=dpsi)
        trigger = clamp(max(0.0, -dpsi) + current_coeff.M + current_coeff.C)
        return evaluate_structural_transition(
            source_phase=source,
            target_phase=target,
            gate_openness=clamp(current_coeff.T),
            carrying_capacity=clamp(current_coeff.N),
            node_fatigue=clamp(current_coeff.C + current_coeff.M, 0.0, 2.0),
            local_safety=clamp(1.0 - max(current_coeff.C, current_coeff.M)),
            continuation_channel=clamp(previous_coeff.T * previous_coeff.N),
            tau=float(max(0, fatigue_counter)),
            tau_star=3.0,
            trigger=trigger,
            source_features=source_features,
            target_features=target_features,
            params=self.params,
        )

    # Backward-compatible alias.
    def evaluate(
        self,
        agent_id: str,
        previous_coeff: Coefficients,
        current_coeff: Coefficients,
        previous_psi: float,
        current_psi: float,
        dpsi: float,
        failure_streak: int,
    ) -> StructuralTransitionReport:
        return self.evaluate_transition(
            entity_id=agent_id,
            previous_coeff=previous_coeff,
            current_coeff=current_coeff,
            previous_psi=previous_psi,
            current_psi=current_psi,
            dpsi=dpsi,
            fatigue_counter=failure_streak,
        )

    @staticmethod
    def report_to_dict(report: StructuralTransitionReport) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "transmissibility": report.transmissibility,
            "retention": report.retention,
            "self_potential": report.self_potential,
            "locked": report.lock_state.locked,
            "transition_gate": report.lock_state.transition_gate,
            "delay_gate": report.delay_gate,
            "compatibility": report.compatibility,
            "transition_channel": report.transition_channel,
            "aftermath": asdict(report.aftermath),
        }
        if report.existence is not None:
            payload["existence"] = asdict(report.existence)
        if report.possibility is not None:
            payload["possibility"] = asdict(report.possibility)
        if report.dynamic_lift is not None:
            payload["dynamic_lift"] = asdict(report.dynamic_lift)
        if report.fate_vector is not None:
            payload["fate_vector"] = asdict(report.fate_vector)
        if report.existence_rank is not None:
            payload["existence_rank"] = report.existence_rank.value
        return payload
