from __future__ import annotations

import math

from .types import AgentTelemetry, Coefficients, HandoffTelemetry, WorkflowTelemetry


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    if not math.isfinite(value):
        return lo
    return max(lo, min(hi, float(value)))


class MetricCoefficientMapper:
    """Maps operational telemetry to Processual AI coefficients T, N, C, M.

    T = synergy/cooperation
    N = need/demand
    C = cost/competition/friction
    M = mortality/transition pressure
    """

    def from_agent_telemetry(self, m: AgentTelemetry) -> Coefficients:
        synergy = clamp(0.45 * m.cooperation_success + 0.35 * m.useful_handoff_rate + 0.20 * m.success_rate)
        need = clamp(
            0.45 * m.demand_rate
            + 0.25 * m.business_priority
            + 0.20 * m.queue_depth
            + 0.10 * m.custom.get("need_boost", 0.0)
        )
        cost = clamp(
            0.35 * m.resource_cost
            + 0.25 * m.overlap_score
            + 0.20 * clamp(m.latency_p95_ms / 10_000.0)
            + 0.20 * m.policy_risk
        )
        mortality = clamp(
            0.40 * clamp(m.failure_count / 10.0)
            + 0.25 * clamp(m.age_seconds / 86_400.0)
            + 0.25 * m.policy_risk
            + 0.10 * clamp(m.latency_p95_ms / 20_000.0)
        )
        return Coefficients(T=synergy, N=need, C=cost, M=mortality)

    # Backward-compatible alias.
    def from_telemetry(self, m: AgentTelemetry) -> Coefficients:
        return self.from_agent_telemetry(m)

    def from_handoff_telemetry(self, h: HandoffTelemetry) -> Coefficients:
        synergy = clamp(
            0.35 * h.artifact_quality
            + 0.30 * h.context_preservation
            + 0.25 * h.acceptance_rate
            + 0.10 * (1.0 - h.ambiguity)
        )
        need = clamp(0.70 * h.demand_rate + 0.30 * h.custom.get("handoff_priority", 0.5))
        cost = clamp(
            0.35 * h.rework_rate + 0.25 * h.ambiguity + 0.20 * clamp(h.latency_ms / 10_000.0) + 0.20 * h.policy_risk
        )
        mortality = clamp(
            0.45 * h.rework_rate + 0.25 * h.ambiguity + 0.20 * h.policy_risk + 0.10 * clamp(h.latency_ms / 20_000.0)
        )
        return Coefficients(T=synergy, N=need, C=cost, M=mortality)

    def from_workflow_telemetry(self, w: WorkflowTelemetry) -> Coefficients:
        synergy = clamp(0.35 * w.coordination_quality + 0.35 * w.goal_alignment + 0.30 * w.completion_confidence)
        need = clamp(0.55 * w.demand_rate + 0.25 * w.custom.get("business_priority", 0.5) + 0.20 * w.progress_rate)
        cost = clamp(0.30 * w.cost_pressure + 0.25 * w.latency_pressure + 0.25 * w.rework_rate + 0.20 * w.blocking_rate)
        mortality = clamp(
            0.35 * w.risk_pressure + 0.25 * w.blocking_rate + 0.25 * w.rework_rate + 0.15 * (1.0 - w.goal_alignment)
        )
        return Coefficients(T=synergy, N=need, C=cost, M=mortality)


class ContinuityEngine:
    """Numerical evaluator of Ψ(t) = integral([(T*N)-C] exp(-M) dt)."""

    def __init__(self, dt: float = 1.0):
        if dt <= 0:
            raise ValueError("dt must be positive")
        self.dt = float(dt)

    def delta(self, coeff: Coefficients) -> float:
        t, n, c, m = clamp(coeff.T), clamp(coeff.N), clamp(coeff.C), clamp(coeff.M)
        return ((t * n) - c) * math.exp(-m) * self.dt

    def step(self, previous_psi: float, coeff: Coefficients) -> tuple[float, float]:
        dpsi = self.delta(coeff)
        return previous_psi + dpsi, dpsi

    @staticmethod
    def normalize_psi(psi: float, scale: float = 2.0) -> float:
        if not math.isfinite(psi):
            return 0.0
        return clamp(1.0 / (1.0 + math.exp(-psi / max(scale, 1e-9))))
