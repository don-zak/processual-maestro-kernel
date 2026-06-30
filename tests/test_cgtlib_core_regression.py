from dataclasses import is_dataclass, replace

import pytest

import cgtlib as cgt
from cgtlib.errors import ValidationError
from cgtlib.invariants import (
    validate_parameters,
    validate_phase_state,
    validate_structural_transition_report,
)
from cgtlib.metadata import build_cgtlib_manifest
from cgtlib.serialization import to_dict
from cgtlib.types import (
    AftermathState,
    CGTParameters,
    FateVector,
    LockState,
    PhaseState,
    StructuralTransitionReport,
)
from cgtlib.validation import (
    ensure_nonnegative,
    ensure_not_empty,
    ensure_unit_interval,
)


def _assert_private_engine_unavailable(exc: BaseException) -> None:
    assert exc.__class__.__name__ == "_FeatureUnavailable"
    assert "private CGT engine" in str(exc)


def _sample_phase(phase_id: str = "phase-a") -> PhaseState:
    return PhaseState(
        phase_id=phase_id,
        mass=1.0,
        mean_retention=0.8,
        harmony=0.75,
        fatigue=0.1,
    )


def _sample_report() -> StructuralTransitionReport:
    return StructuralTransitionReport(
        transmissibility=0.7,
        retention=0.72,
        self_potential=0.4,
        lock_state=LockState(
            locked=True,
            self_potential=0.4,
            transition_gate=0.1,
            lock_threshold=0.3,
            lock_gate_max=0.2,
        ),
        delay_gate=0.6,
        compatibility=0.75,
        transition_channel=0.35,
        aftermath=AftermathState(
            collapse_score=0.1,
            flourishing_score=0.65,
            balance=0.55,
        ),
        fate_vector=FateVector(
            stability=0.7,
            hybridity=0.2,
            distortion=0.1,
            extinction=0.05,
            collapse=0.08,
            flourishing=0.6,
            balance=0.55,
        ),
    )


def test_public_top_level_exports_core_symbols_and_fallback_wrappers():
    expected_symbols = (
        "CGTParameters",
        "PhaseState",
        "StructuralTransitionReport",
        "ExistenceRank",
        "FateVector",
        "compute_phase_mass",
        "compute_self_potential",
        "compute_transmissibility",
        "compute_delay_gate",
        "compute_transition_channel",
        "compute_retention",
        "compute_compatibility",
        "evaluate_fate_vector",
        "classify_existence_rank",
        "evaluate_existence",
        "evaluate_structural_transition",
        "evaluate_transition_batch",
        "summarize_transition_batch",
        "validate_parameters",
        "validate_phase_state",
        "validate_structural_transition_report",
        "simulate_delay_progression",
        "simulate_transition_series",
        "build_cgtlib_manifest",
    )

    for symbol in expected_symbols:
        assert hasattr(cgt, symbol), symbol


def test_private_engine_dependent_top_level_wrappers_fail_clearly():
    unavailable_calls = [
        lambda: cgt.build_public_api_snapshot(),
        lambda: cgt.compute_phase_mass([0.2, 0.3, 0.5]),
        lambda: cgt.compute_existential_score(0.9, 0.8, 0.7),
        lambda: cgt.canonical_phase_state(
            "phase",
            mass=1.0,
            mean_retention=0.8,
            harmony=0.75,
            fatigue=0.1,
        ),
        lambda: cgt.evaluate_fate_vector(
            retention=0.8,
            harmony=0.75,
            compatibility=0.7,
            distortion=0.1,
        ),
        lambda: cgt.validate_parameters(CGTParameters()),
        lambda: cgt.validate_phase_state(_sample_phase()),
    ]

    for call in unavailable_calls:
        with pytest.raises(Exception) as exc_info:
            call()
        _assert_private_engine_unavailable(exc_info.value)


def test_public_validation_primitives_work_without_private_engine():
    assert ensure_unit_interval(0.5, "value") == 0.5
    assert ensure_nonnegative(0.0, "value") == 0.0
    assert ensure_not_empty([1], "items") == [1]

    with pytest.raises(ValidationError):
        ensure_unit_interval(-0.1, "value")

    with pytest.raises(ValidationError):
        ensure_unit_interval(1.1, "value")

    with pytest.raises(ValidationError):
        ensure_nonnegative(-1.0, "value")

    with pytest.raises(ValidationError):
        ensure_not_empty([], "items")


def test_public_types_and_invariants_work_without_private_engine():
    params = CGTParameters()

    assert is_dataclass(params)
    assert validate_parameters(params) is params

    bad_params = replace(params, lock_gate_max=1.5)
    with pytest.raises(ValidationError):
        validate_parameters(bad_params)

    phase = _sample_phase("phase-valid")

    assert is_dataclass(phase)
    assert validate_phase_state(phase) is phase

    bad_retention = replace(phase, mean_retention=1.5)
    with pytest.raises(ValidationError):
        validate_phase_state(bad_retention)

    empty_id = replace(phase, phase_id=" ")
    with pytest.raises(ValidationError):
        validate_phase_state(empty_id)


def test_structural_report_invariants_and_serialization_are_stable():
    report = _sample_report()

    assert validate_structural_transition_report(report) is report

    report_dict = to_dict(report)

    assert report_dict["transmissibility"] == 0.7
    assert report_dict["retention"] == 0.72
    assert report_dict["lock_state"]["locked"] is True
    assert report_dict["aftermath"]["balance"] == 0.55
    assert report_dict["fate_vector"]["stability"] == 0.7

    bad_report = replace(
        report,
        transition_channel=1.5,
    )
    with pytest.raises(ValidationError):
        validate_structural_transition_report(bad_report)

    bad_lock = replace(
        report,
        lock_state=LockState(
            locked=True,
            self_potential=0.4,
            transition_gate=0.9,
            lock_threshold=0.3,
            lock_gate_max=0.2,
        ),
    )
    with pytest.raises(ValidationError):
        validate_structural_transition_report(bad_lock)


def test_manifest_and_dataclass_serialization_are_available_publicly():
    manifest = build_cgtlib_manifest()

    assert manifest["library"] == "cgtlib"
    assert "version" in manifest
    assert "public_modules" in manifest
    assert "private_modules" in manifest

    fate = FateVector(
        stability=0.7,
        hybridity=0.2,
        distortion=0.1,
        extinction=0.05,
        collapse=0.08,
        flourishing=0.6,
        balance=0.55,
    )

    fate_dict = to_dict(fate)

    assert fate_dict == {
        "stability": 0.7,
        "hybridity": 0.2,
        "distortion": 0.1,
        "extinction": 0.05,
        "collapse": 0.08,
        "flourishing": 0.6,
        "balance": 0.55,
    }

    phase_dict = to_dict(_sample_phase("phase-serial"))

    assert phase_dict["phase_id"] == "phase-serial"
    assert phase_dict["mass"] == 1.0
    assert phase_dict["mean_retention"] == 0.8
    assert phase_dict["harmony"] == 0.75
    assert phase_dict["fatigue"] == 0.1