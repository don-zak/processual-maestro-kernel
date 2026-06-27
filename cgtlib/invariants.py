from __future__ import annotations

import math

from .errors import ValidationError
from .types import CGTParameters, PhaseState, StructuralTransitionReport
from .validation import ensure_nonnegative, ensure_unit_interval


def _ensure_bounded(value: float, name: str, *, minimum: float, maximum: float) -> float:
    if not math.isfinite(value):
        raise ValidationError(f"{name} must be finite")
    if value < minimum or value > maximum:
        raise ValidationError(f"{name} must be within [{minimum}, {maximum}]")
    return value


def validate_phase_state(phase: PhaseState) -> PhaseState:
    if not phase.phase_id.strip():
        raise ValidationError("phase.phase_id must not be empty")
    ensure_nonnegative(phase.mass, "phase.mass")
    ensure_unit_interval(phase.mean_retention, "phase.mean_retention")
    ensure_unit_interval(phase.harmony, "phase.harmony")
    ensure_nonnegative(phase.fatigue, "phase.fatigue")
    if phase.self_potential is not None:
        _ensure_bounded(phase.self_potential, "phase.self_potential", minimum=-1.0e6, maximum=1.0e6)
    return phase


def validate_parameters(params: CGTParameters) -> CGTParameters:
    ensure_nonnegative(params.lam, "params.lam")
    ensure_nonnegative(params.omega, "params.omega")
    ensure_nonnegative(params.mu, "params.mu")
    ensure_unit_interval(params.lock_threshold, "params.lock_threshold")
    ensure_unit_interval(params.lock_gate_max, "params.lock_gate_max")
    ensure_nonnegative(params.logistic_k, "params.logistic_k")
    return params


def validate_structural_transition_report(report: StructuralTransitionReport) -> StructuralTransitionReport:
    ensure_unit_interval(report.transmissibility, "report.transmissibility")
    ensure_unit_interval(report.retention, "report.retention")
    _ensure_bounded(report.self_potential, "report.self_potential", minimum=-1.0e6, maximum=1.0e6)
    ensure_unit_interval(report.delay_gate, "report.delay_gate")
    ensure_unit_interval(report.compatibility, "report.compatibility")
    ensure_unit_interval(report.transition_channel, "report.transition_channel")
    _ensure_bounded(report.aftermath.collapse_score, "report.aftermath.collapse_score", minimum=0.0, maximum=1.0)
    _ensure_bounded(report.aftermath.flourishing_score, "report.aftermath.flourishing_score", minimum=0.0, maximum=1.0)
    _ensure_bounded(report.aftermath.balance, "report.aftermath.balance", minimum=-1.0, maximum=1.0)
    if report.existence is not None:
        ensure_unit_interval(report.existence.origin, "report.existence.origin")
        ensure_unit_interval(report.existence.carrier, "report.existence.carrier")
        ensure_unit_interval(report.existence.effect, "report.existence.effect")
        ensure_unit_interval(report.existence.score, "report.existence.score")
    if report.possibility is not None:
        ensure_unit_interval(report.possibility.raw_potential, "report.possibility.raw_potential")
        ensure_unit_interval(report.possibility.constraint, "report.possibility.constraint")
        ensure_unit_interval(report.possibility.carrier, "report.possibility.carrier")
        ensure_unit_interval(report.possibility.score, "report.possibility.score")
    if report.dynamic_lift is not None:
        ensure_nonnegative(report.dynamic_lift.dwell_time, "report.dynamic_lift.dwell_time")
        ensure_unit_interval(report.dynamic_lift.pressure, "report.dynamic_lift.pressure")
        ensure_unit_interval(report.dynamic_lift.carrier, "report.dynamic_lift.carrier")
        ensure_unit_interval(report.dynamic_lift.overload, "report.dynamic_lift.overload")
        ensure_unit_interval(report.dynamic_lift.lift, "report.dynamic_lift.lift")
    if report.fate_vector is not None:
        ensure_unit_interval(report.fate_vector.stability, "report.fate_vector.stability")
        ensure_unit_interval(report.fate_vector.hybridity, "report.fate_vector.hybridity")
        ensure_unit_interval(report.fate_vector.distortion, "report.fate_vector.distortion")
        ensure_unit_interval(report.fate_vector.extinction, "report.fate_vector.extinction")
        ensure_unit_interval(report.fate_vector.collapse, "report.fate_vector.collapse")
        ensure_unit_interval(report.fate_vector.flourishing, "report.fate_vector.flourishing")
        _ensure_bounded(report.fate_vector.balance, "report.fate_vector.balance", minimum=-1.0, maximum=1.0)
    if report.lock_state.transition_gate > report.lock_state.lock_gate_max and report.lock_state.locked:
        raise ValidationError("locked reports must not exceed lock_state.lock_gate_max")
    return report
