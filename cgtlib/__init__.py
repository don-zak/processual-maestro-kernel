"""cgtlib v2.0 - public formal-core surface for CGT."""

from __future__ import annotations

from .aftermath import (
    compute_aftermath_balance,
    compute_collapse_indicator,
    compute_flourishing_indicator,
)
from .api import CGTLIB_STABLE_API, build_public_api_snapshot
from .batch import (
    StructuralTransitionInput,
    evaluate_transition_batch,
    summarize_transition_batch,
    validate_transition_batch_inputs,
)
from .benchmark_surfaces import (
    BenchmarkSurface,
    BenchmarkSurfacePoint,
    evaluate_benchmark_surface,
    evaluate_benchmark_surfaces,
    summarize_benchmark_surface,
)
from .catalogs import (
    build_all_canonical_scenario_packs,
    build_canonical_scenario_pack,
    list_canonical_scenario_catalog,
)
from .comparative_envelopes import (
    ComparativeEnvelope,
    ComparativeEnvelopeReport,
    evaluate_comparative_envelopes,
    summarize_comparative_envelopes,
)
from .compatibility import compute_compatibility
from .evaluators import (
    evaluate_aftermath,
    evaluate_compatibility,
    evaluate_continuation,
    evaluate_locking,
    evaluate_structural_transition,
)
from .existence import compute_existential_score, evaluate_existence
from .fate import (
    classify_existence_rank,
    compute_distortion_indicator,
    compute_extinction_indicator,
    compute_fate_balance,
    compute_flourishing_potential,
    compute_hybridity_indicator,
    compute_repeatability,
    compute_stability_indicator,
    evaluate_fate_vector,
)
from .fixtures import canonical_phase_state, canonical_scenario_pack, canonical_transition_input
from .gates import compute_delay_gate, compute_transition_channel, compute_transmissibility
from .invariants import validate_parameters, validate_phase_state, validate_structural_transition_report
from .lift import compute_dynamic_lift, evaluate_dynamic_lift
from .locking import evaluate_lock_state
from .metadata import (
    CGTLIB_API_STAGE,
    CGTLIB_BOUNDARY_STATUS,
    CGTLIB_FORBIDDEN_INTEGRATION_DOMAINS,
    CGTLIB_PUBLIC_MODULES,
    CGTLIB_VERSION,
    build_cgtlib_manifest,
)
from .phase import compute_phase_mass, compute_self_potential
from .possibility import compute_constrained_possibility, evaluate_possibility
from .reference_data import (
    ReferenceScenarioRecord,
    list_reference_dataset_ids,
    load_all_reference_scenario_records,
    load_reference_scenario_packs,
    load_reference_scenario_record,
)
from .regime_classifiers import (
    RegimeClassification,
    RegimeClassifierReport,
    classify_comparative_envelopes,
    classify_robustness_report,
    evaluate_canonical_regime_classifier_report,
)
from .retention import compute_retention
from .robustness import RobustnessReport, evaluate_multi_axis_robustness, summarize_robustness_report
from .robustness_profiles import (
    RobustnessProfile,
    evaluate_all_canonical_robustness_profiles,
    evaluate_canonical_robustness_profile,
    list_canonical_robustness_profiles,
    load_canonical_robustness_profile,
)
from .scenarios import (
    ScenarioPack,
    ScenarioPackResult,
    evaluate_scenario_pack,
    evaluate_scenario_packs,
    summarize_scenario_packs,
    validate_scenario_pack,
)
from .sensitivity import (
    SensitivityReport,
    SensitivitySnapshot,
    evaluate_parameter_sensitivity,
    summarize_sensitivity_report,
)
from .simulation import simulate_delay_progression, simulate_transition_series
from .stress_regimes import (
    StressRegime,
    evaluate_all_canonical_stress_regimes,
    evaluate_canonical_stress_regime,
    list_canonical_stress_regimes,
    load_canonical_stress_regime,
)
from .trajectory_maps import (
    TrajectoryMap,
    TrajectoryMapPoint,
    evaluate_regime_trajectory_map,
    summarize_trajectory_map,
)
from .transition_archetypes import (
    TransitionArchetype,
    evaluate_all_canonical_transition_archetypes,
    evaluate_canonical_transition_archetype,
    list_canonical_transition_archetypes,
    load_canonical_transition_archetype,
    summarize_all_transition_archetypes,
    summarize_transition_archetype,
)
from .types import (
    AftermathState,
    CGTParameters,
    CompatibilityState,
    DynamicLiftState,
    ExistenceRank,
    ExistenceState,
    FateVector,
    GateState,
    LockState,
    NodeState,
    PhaseState,
    PossibilityState,
    StructuralTransitionReport,
)

# The public distribution never discovers or imports the proprietary engine.
# Private execution is composed outside this artifact through the controlled
# trust boundary, so this value is intentionally constant in public builds.
_HAS_PRIVATE = False

# Retain the historic public aliases without attempting private discovery.
summarize_multi_axis_robustness = evaluate_multi_axis_robustness
summarize_parameter_sensitivity = evaluate_parameter_sensitivity
summarize_regime_trajectory_map = evaluate_regime_trajectory_map

__all__ = [
    "AftermathState",
    "CGTLIB_VERSION",
    "CGTLIB_STABLE_API",
    "CGTLIB_PUBLIC_MODULES",
    "CGTLIB_FORBIDDEN_INTEGRATION_DOMAINS",
    "CGTLIB_BOUNDARY_STATUS",
    "CGTLIB_API_STAGE",
    "CGTParameters",
    "CompatibilityState",
    "build_all_canonical_scenario_packs",
    "build_canonical_scenario_pack",
    "list_canonical_scenario_catalog",
    "ReferenceScenarioRecord",
    "list_reference_dataset_ids",
    "load_all_reference_scenario_records",
    "load_reference_scenario_packs",
    "load_reference_scenario_record",
    "canonical_phase_state",
    "canonical_scenario_pack",
    "canonical_transition_input",
    "StructuralTransitionInput",
    "ScenarioPack",
    "ScenarioPackResult",
    "BenchmarkSurface",
    "BenchmarkSurfacePoint",
    "SensitivityReport",
    "SensitivitySnapshot",
    "RobustnessReport",
    "RobustnessProfile",
    "ComparativeEnvelope",
    "ComparativeEnvelopeReport",
    "StressRegime",
    "RegimeClassification",
    "RegimeClassifierReport",
    "TransitionArchetype",
    "TrajectoryMap",
    "TrajectoryMapPoint",
    "GateState",
    "LockState",
    "NodeState",
    "PhaseState",
    "StructuralTransitionReport",
    "evaluate_fate_vector",
    "classify_existence_rank",
    "compute_fate_balance",
    "compute_flourishing_potential",
    "compute_extinction_indicator",
    "compute_stability_indicator",
    "compute_distortion_indicator",
    "compute_hybridity_indicator",
    "compute_repeatability",
    "evaluate_dynamic_lift",
    "compute_dynamic_lift",
    "evaluate_possibility",
    "compute_constrained_possibility",
    "evaluate_existence",
    "compute_existential_score",
    "ExistenceRank",
    "FateVector",
    "DynamicLiftState",
    "PossibilityState",
    "ExistenceState",
    "compute_aftermath_balance",
    "build_cgtlib_manifest",
    "build_public_api_snapshot",
    "compute_collapse_indicator",
    "compute_compatibility",
    "evaluate_transition_batch",
    "compute_delay_gate",
    "evaluate_scenario_pack",
    "evaluate_scenario_packs",
    "summarize_scenario_packs",
    "evaluate_parameter_sensitivity",
    "summarize_sensitivity_report",
    "evaluate_benchmark_surface",
    "evaluate_benchmark_surfaces",
    "summarize_benchmark_surface",
    "evaluate_multi_axis_robustness",
    "summarize_robustness_report",
    "list_canonical_robustness_profiles",
    "load_canonical_robustness_profile",
    "evaluate_canonical_robustness_profile",
    "evaluate_all_canonical_robustness_profiles",
    "evaluate_comparative_envelopes",
    "summarize_comparative_envelopes",
    "list_canonical_stress_regimes",
    "load_canonical_stress_regime",
    "evaluate_canonical_stress_regime",
    "evaluate_all_canonical_stress_regimes",
    "classify_robustness_report",
    "classify_comparative_envelopes",
    "evaluate_canonical_regime_classifier_report",
    "list_canonical_transition_archetypes",
    "load_canonical_transition_archetype",
    "evaluate_canonical_transition_archetype",
    "evaluate_all_canonical_transition_archetypes",
    "summarize_transition_archetype",
    "summarize_all_transition_archetypes",
    "evaluate_regime_trajectory_map",
    "summarize_trajectory_map",
    "validate_parameters",
    "validate_phase_state",
    "validate_structural_transition_report",
    "validate_scenario_pack",
    "compute_flourishing_indicator",
    "compute_phase_mass",
    "compute_retention",
    "compute_self_potential",
    "compute_transition_channel",
    "compute_transmissibility",
    "evaluate_aftermath",
    "evaluate_compatibility",
    "evaluate_continuation",
    "evaluate_lock_state",
    "evaluate_locking",
    "evaluate_structural_transition",
    "summarize_multi_axis_robustness",
    "summarize_parameter_sensitivity",
    "summarize_regime_trajectory_map",
    "summarize_transition_batch",
    "validate_transition_batch_inputs",
    "simulate_delay_progression",
    "simulate_transition_series",
]
