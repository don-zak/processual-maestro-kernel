"""Fallback stubs for when cgtlib/private/ is unavailable (public build).

Each function returns a structured error response indicating the private CGT
engine is not available.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_UNAVAILABLE_MSG = "requires private CGT engine which is not available in this build"


class _FeatureUnavailable(Exception):
    def __init__(self, feature: str = "CGT") -> None:
        super().__init__(f"{feature} {_UNAVAILABLE_MSG}")


def _error_result() -> dict[str, Any]:
    return {"error": "private_cgt_engine_unavailable", "message": _UNAVAILABLE_MSG}


# ---------- evaluators ----------
def evaluate_structural_transition(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_structural_transition")


def evaluate_continuation(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_continuation")


def evaluate_locking(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_locking")


def evaluate_compatibility(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_compatibility")


def evaluate_aftermath(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_aftermath")


# ---------- fate ----------
def evaluate_fate_vector(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_fate_vector")


def classify_existence_rank(*args, **kwargs):
    raise _FeatureUnavailable("classify_existence_rank")


def compute_fate_balance(*args, **kwargs):
    raise _FeatureUnavailable("compute_fate_balance")


def compute_flourishing_potential(*args, **kwargs):
    raise _FeatureUnavailable("compute_flourishing_potential")


def compute_extinction_indicator(*args, **kwargs):
    raise _FeatureUnavailable("compute_extinction_indicator")


def compute_stability_indicator(*args, **kwargs):
    raise _FeatureUnavailable("compute_stability_indicator")


def compute_distortion_indicator(*args, **kwargs):
    raise _FeatureUnavailable("compute_distortion_indicator")


def compute_hybridity_indicator(*args, **kwargs):
    raise _FeatureUnavailable("compute_hybridity_indicator")


def compute_repeatability(*args, **kwargs):
    raise _FeatureUnavailable("compute_repeatability")


# ---------- gates / retention / phase / locking / lift / possibility / existence ----------
def compute_delay_gate(*args, **kwargs):
    raise _FeatureUnavailable("compute_delay_gate")


def compute_transition_channel(*args, **kwargs):
    raise _FeatureUnavailable("compute_transition_channel")


def compute_transmissibility(*args, **kwargs):
    raise _FeatureUnavailable("compute_transmissibility")


def compute_retention(*args, **kwargs):
    raise _FeatureUnavailable("compute_retention")


def compute_phase_mass(*args, **kwargs):
    raise _FeatureUnavailable("compute_phase_mass")


def compute_self_potential(*args, **kwargs):
    raise _FeatureUnavailable("compute_self_potential")


def evaluate_lock_state(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_lock_state")


def compute_dynamic_lift(*args, **kwargs):
    raise _FeatureUnavailable("compute_dynamic_lift")


def evaluate_dynamic_lift(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_dynamic_lift")


def compute_constrained_possibility(*args, **kwargs):
    raise _FeatureUnavailable("compute_constrained_possibility")


def evaluate_possibility(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_possibility")


def evaluate_existence(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_existence")


def compute_existential_score(*args, **kwargs):
    raise _FeatureUnavailable("compute_existential_score")


def compute_aftermath_balance(*args, **kwargs):
    raise _FeatureUnavailable("compute_aftermath_balance")


def compute_collapse_indicator(*args, **kwargs):
    raise _FeatureUnavailable("compute_collapse_indicator")


def compute_flourishing_indicator(*args, **kwargs):
    raise _FeatureUnavailable("compute_flourishing_indicator")


def compute_compatibility(*args, **kwargs):
    raise _FeatureUnavailable("compute_compatibility")


# ---------- batch / simulation / scenarios ----------
def evaluate_transition_batch(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_transition_batch")


def summarize_transition_batch(*args, **kwargs):
    raise _FeatureUnavailable("summarize_transition_batch")


def validate_transition_batch_inputs(*args, **kwargs):
    raise _FeatureUnavailable("validate_transition_batch_inputs")


def simulate_delay_progression(*args, **kwargs):
    raise _FeatureUnavailable("simulate_delay_progression")


def simulate_transition_series(*args, **kwargs):
    raise _FeatureUnavailable("simulate_transition_series")


def evaluate_scenario_pack(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_scenario_pack")


def evaluate_scenario_packs(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_scenario_packs")


def summarize_scenario_packs(*args, **kwargs):
    raise _FeatureUnavailable("summarize_scenario_packs")


def validate_scenario_pack(*args, **kwargs):
    raise _FeatureUnavailable("validate_scenario_pack")


# ---------- higher-order analysis ----------
def evaluate_parameter_sensitivity(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_parameter_sensitivity")


def summarize_sensitivity_report(*args, **kwargs):
    raise _FeatureUnavailable("summarize_sensitivity_report")


def evaluate_benchmark_surface(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_benchmark_surface")


def evaluate_benchmark_surfaces(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_benchmark_surfaces")


def summarize_benchmark_surface(*args, **kwargs):
    raise _FeatureUnavailable("summarize_benchmark_surface")


def evaluate_multi_axis_robustness(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_multi_axis_robustness")


def summarize_robustness_report(*args, **kwargs):
    raise _FeatureUnavailable("summarize_robustness_report")


def evaluate_comparative_envelopes(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_comparative_envelopes")


def summarize_comparative_envelopes(*args, **kwargs):
    raise _FeatureUnavailable("summarize_comparative_envelopes")


def evaluate_canonical_regime_classifier_report(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_canonical_regime_classifier_report")


def classify_robustness_report(*args, **kwargs):
    raise _FeatureUnavailable("classify_robustness_report")


def classify_comparative_envelopes(*args, **kwargs):
    raise _FeatureUnavailable("classify_comparative_envelopes")


def evaluate_regime_trajectory_map(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_regime_trajectory_map")


def summarize_trajectory_map(*args, **kwargs):
    raise _FeatureUnavailable("summarize_trajectory_map")


def evaluate_canonical_stress_regime(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_canonical_stress_regime")


def evaluate_all_canonical_stress_regimes(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_all_canonical_stress_regimes")


def list_canonical_stress_regimes():
    raise _FeatureUnavailable("list_canonical_stress_regimes")


def load_canonical_stress_regime(*args, **kwargs):
    raise _FeatureUnavailable("load_canonical_stress_regime")


def evaluate_all_canonical_robustness_profiles(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_all_canonical_robustness_profiles")


def evaluate_canonical_robustness_profile(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_canonical_robustness_profile")


def list_canonical_robustness_profiles():
    raise _FeatureUnavailable("list_canonical_robustness_profiles")


def load_canonical_robustness_profile(*args, **kwargs):
    raise _FeatureUnavailable("load_canonical_robustness_profile")


def evaluate_transition_archetype(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_transition_archetype")


def evaluate_all_canonical_transition_archetypes(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_all_canonical_transition_archetypes")


def evaluate_canonical_transition_archetype(*args, **kwargs):
    raise _FeatureUnavailable("evaluate_canonical_transition_archetype")


def list_canonical_transition_archetypes():
    raise _FeatureUnavailable("list_canonical_transition_archetypes")


def load_canonical_transition_archetype(*args, **kwargs):
    raise _FeatureUnavailable("load_canonical_transition_archetype")


def summarize_transition_archetype(*args, **kwargs):
    raise _FeatureUnavailable("summarize_transition_archetype")


def summarize_all_transition_archetypes(*args, **kwargs):
    raise _FeatureUnavailable("summarize_all_transition_archetypes")


# ---------- catalogs / fixtures / reference data ----------
def build_canonical_scenario_pack(*args, **kwargs):
    raise _FeatureUnavailable("build_canonical_scenario_pack")


def build_all_canonical_scenario_packs(*args, **kwargs):
    raise _FeatureUnavailable("build_all_canonical_scenario_packs")


def list_canonical_scenario_catalog():
    raise _FeatureUnavailable("list_canonical_scenario_catalog")


def canonical_phase_state(*args, **kwargs):
    raise _FeatureUnavailable("canonical_phase_state")


def canonical_scenario_pack(*args, **kwargs):
    raise _FeatureUnavailable("canonical_scenario_pack")


def canonical_transition_input(*args, **kwargs):
    raise _FeatureUnavailable("canonical_transition_input")


def list_reference_dataset_ids():
    raise _FeatureUnavailable("list_reference_dataset_ids")


def load_all_reference_scenario_records(*args, **kwargs):
    raise _FeatureUnavailable("load_all_reference_scenario_records")


def load_reference_scenario_packs(*args, **kwargs):
    raise _FeatureUnavailable("load_reference_scenario_packs")


def load_reference_scenario_record(*args, **kwargs):
    raise _FeatureUnavailable("load_reference_scenario_record")


# ---------- invariants ----------
def validate_parameters(*args, **kwargs):
    raise _FeatureUnavailable("validate_parameters")


def validate_phase_state(*args, **kwargs):
    raise _FeatureUnavailable("validate_phase_state")


def validate_structural_transition_report(*args, **kwargs):
    raise _FeatureUnavailable("validate_structural_transition_report")


# ---------- api / metadata ----------
CGTLIB_STABLE_API: dict[str, Any] = field(default_factory=lambda: {"_available": False})


def build_public_api_snapshot(*args, **kwargs):
    raise _FeatureUnavailable("build_public_api_snapshot")


def build_cgtlib_manifest():
    from .metadata import CGTLIB_PRIVATE_MODULES, CGTLIB_PUBLIC_MODULES, CGTLIB_VERSION, CGTLIB_API_STAGE, CGTLIB_BOUNDARY_STATUS

    return {
        "library": "cgtlib",
        "version": CGTLIB_VERSION,
        "api_stage": CGTLIB_API_STAGE,
        "boundary_status": CGTLIB_BOUNDARY_STATUS,
        "public_modules": list(CGTLIB_PUBLIC_MODULES),
        "private_modules": list(CGTLIB_PRIVATE_MODULES),
        "equations_version": "private-not-available",
        "note": "private CGT engine not available in this build",
    }
