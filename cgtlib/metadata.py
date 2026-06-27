from __future__ import annotations

from typing import Final

CGTLIB_VERSION: Final[str] = "1.0.0"
CGTLIB_API_STAGE: Final[str] = "v1.0-final-standalone-formal-core"
CGTLIB_BOUNDARY_STATUS: Final[str] = "standalone-finalized"
CGTLIB_FORBIDDEN_INTEGRATION_DOMAINS: Final[tuple[str, ...]] = (
    "providers",
    "readiness",
    "replay",
    "eval bundles",
    "console payloads",
    "training campaigns",
    "deployment briefs",
)
CGTLIB_PUBLIC_MODULES: Final[tuple[str, ...]] = (
    "types",
    "validation",
    "gates",
    "retention",
    "phase",
    "locking",
    "compatibility",
    "aftermath",
    "fate",
    "lift",
    "possibility",
    "existence",
    "evaluators",
    "simulation",
    "serialization",
    "batch",
    "invariants",
    "scenarios",
    "fixtures",
    "catalogs",
    "reference_data",
    "sensitivity",
    "benchmark_surfaces",
    "robustness",
    "robustness_profiles",
    "comparative_envelopes",
    "stress_regimes",
    "regime_classifiers",
    "transition_archetypes",
    "trajectory_maps",
    "api",
    "metadata",
)


CGTLIB_PRIVATE_MODULES: Final[tuple[str, ...]] = (
    "private.equations",
    "private.constants",
    "private.thresholds",
    "private.calibration",
    "private.version",
    "private.compute",
)


def build_cgtlib_manifest() -> dict[str, object]:
    try:
        from .private.version import CGT_EQUATIONS_VERSION as _eq_ver  # noqa: N811
        eq_ver = _eq_ver
    except ModuleNotFoundError:
        eq_ver = "private-not-available"

    return {
        "library": "cgtlib",
        "version": CGTLIB_VERSION,
        "api_stage": CGTLIB_API_STAGE,
        "boundary_status": CGTLIB_BOUNDARY_STATUS,
        "public_modules": list(CGTLIB_PUBLIC_MODULES),
        "private_modules": list(CGTLIB_PRIVATE_MODULES),
        "equations_version": eq_ver,
        "forbidden_integration_domains": list(CGTLIB_FORBIDDEN_INTEGRATION_DOMAINS),
    }
