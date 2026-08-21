from __future__ import annotations

import importlib
import sys

import pytest

from cgtlib import _fallback


PUBLIC_MODULES = (
    "cgtlib.aftermath",
    "cgtlib.compatibility",
    "cgtlib.evaluators",
    "cgtlib.existence",
    "cgtlib.fate",
    "cgtlib.gates",
    "cgtlib.lift",
    "cgtlib.locking",
    "cgtlib.phase",
    "cgtlib.possibility",
    "cgtlib.reference_data",
    "cgtlib.retention",
)


def test_public_cgt_modules_import_without_private_engine() -> None:
    for module_name in PUBLIC_MODULES:
        module = importlib.import_module(module_name)
        assert module is not None

    assert "cgtlib.private" not in sys.modules


def test_reference_data_remains_available_without_private_math() -> None:
    from cgtlib.reference_data import list_reference_dataset_ids

    assert list_reference_dataset_ids() == (
        "balanced_transition_band",
        "stress_recovery_band",
        "boundary_lock_band",
    )


def test_protected_public_math_fails_closed_with_generic_error() -> None:
    from cgtlib.gates import compute_delay_gate

    with pytest.raises(_fallback._FeatureUnavailableError) as exc_info:
        compute_delay_gate(1.0, 2.0, 3.0)

    rendered = str(exc_info.value)
    assert "requires private CGT engine" in rendered
    for forbidden in ("equation", "threshold", "weight", "calibration", "vector"):
        assert forbidden not in rendered.lower()
