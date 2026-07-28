from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from processual_api.billing.maestro_calibration_contracts import (
    APPROVED_FOR_CHECKOUT,
    APPROVED_FOR_INVOICING,
    APPROVED_FOR_QUOTA,
    CALIBRATION_VERSION,
    SHADOW_ONLY,
    CalibrationQuantities,
    CalibrationValidationError,
    CalibrationWorkload,
    MaestroBillingDisposition,
    MaestroFailureOwner,
    MaestroResourceBand,
    MaestroTaskFamily,
)


def make_workload(**overrides):
    values = {
        "workload_id": "TEST-01",
        "title": "Test",
        "task_family": MaestroTaskFamily.AUTOMATION_EXECUTION,
        "quantities": CalibrationQuantities(base_executions=Decimal(1)),
        "resource_band": MaestroResourceBand.NORMAL,
        "expected_failure_owner": MaestroFailureOwner.NONE,
        "expected_disposition": MaestroBillingDisposition.SETTLED,
        "expected_raw_units": Decimal(1),
        "expected_settled_units": Decimal(1),
    }
    values.update(overrides)
    return CalibrationWorkload(**values)


def test_calibration_is_explicitly_shadow_only():
    assert CALIBRATION_VERSION == "maestro-unit-v1-calibration-a"
    assert SHADOW_ONLY is True
    assert APPROVED_FOR_QUOTA is False
    assert APPROVED_FOR_INVOICING is False
    assert APPROVED_FOR_CHECKOUT is False


def test_contracts_require_decimal_and_non_negative_values():
    with pytest.raises(CalibrationValidationError):
        CalibrationQuantities(base_executions=1)  # type: ignore[arg-type]
    with pytest.raises(CalibrationValidationError):
        CalibrationQuantities(base_executions=Decimal(-1))
    with pytest.raises(CalibrationValidationError):
        CalibrationQuantities(base_executions=Decimal("NaN"))


def test_platform_failure_must_settle_zero():
    with pytest.raises(CalibrationValidationError):
        make_workload(
            expected_failure_owner=MaestroFailureOwner.PLATFORM,
            expected_settled_units=Decimal(1),
        )


def test_non_billable_must_settle_zero():
    with pytest.raises(CalibrationValidationError):
        make_workload(
            expected_disposition=MaestroBillingDisposition.NON_BILLABLE,
            expected_settled_units=Decimal(1),
        )


def test_custom_workload_cannot_auto_settle():
    with pytest.raises(CalibrationValidationError):
        make_workload(
            resource_band=MaestroResourceBand.CUSTOM,
            expected_settled_units=Decimal(1),
        )


def test_dataclasses_are_frozen():
    workload = make_workload()
    with pytest.raises(FrozenInstanceError):
        workload.title = "changed"  # type: ignore[misc]


def test_serialization_is_stable_and_stringifies_decimals():
    serialized = make_workload().to_dict()
    assert serialized["expected_raw_units"] == "1"
    assert serialized["quantities"]["base_executions"] == "1"
    assert serialized["task_family"] == "automation_execution"
