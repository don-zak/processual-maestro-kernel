from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from processual_api.billing.maestro_calibration_contracts import (
    CalibrationQuantities,
    MaestroBillingDisposition,
    MaestroFailureOwner,
    MaestroResourceBand,
    MaestroTaskFamily,
)
from processual_api.billing.maestro_shadow_measurements import (
    APPROVED_FOR_CHECKOUT,
    APPROVED_FOR_INVOICING,
    APPROVED_FOR_QUOTA,
    APPROVED_FOR_RUNTIME_ENFORCEMENT,
    SHADOW_ONLY,
    MaestroShadowMeasurement,
    ShadowMeasurementOutcome,
    ShadowMeasurementValidationError,
)


def make_measurement(**overrides):
    values = {
        "measurement_id": "measure-001",
        "execution_id": "execution-001",
        "attempt_id": "attempt-001",
        "observed_at": datetime(2026, 7, 28, tzinfo=UTC),
        "task_family": MaestroTaskFamily.AUTOMATION_EXECUTION,
        "outcome": ShadowMeasurementOutcome.COMPLETED,
        "quantities": CalibrationQuantities(base_executions=Decimal("1")),
        "resource_band": MaestroResourceBand.NORMAL,
        "failure_owner": MaestroFailureOwner.NONE,
        "disposition": MaestroBillingDisposition.SETTLED,
        "duration_ms": Decimal("125.5"),
        "estimated_provider_cost": Decimal("0.02"),
        "estimated_infrastructure_cost": Decimal("0.01"),
    }
    values.update(overrides)
    return MaestroShadowMeasurement(**values)


def test_r2_measurements_are_explicitly_shadow_only():
    assert SHADOW_ONLY is True
    assert APPROVED_FOR_QUOTA is False
    assert APPROVED_FOR_INVOICING is False
    assert APPROVED_FOR_CHECKOUT is False
    assert APPROVED_FOR_RUNTIME_ENFORCEMENT is False


def test_measurement_requires_decimal_costs_and_duration():
    with pytest.raises(ShadowMeasurementValidationError):
        make_measurement(duration_ms=1.5)

    with pytest.raises(ShadowMeasurementValidationError):
        make_measurement(estimated_provider_cost=Decimal("-0.01"))


def test_measurement_requires_utc_timestamp():
    with pytest.raises(ShadowMeasurementValidationError):
        make_measurement(observed_at=datetime(2026, 7, 28))


def test_identifier_validation_rejects_sensitive_shapes():
    with pytest.raises(ShadowMeasurementValidationError):
        make_measurement(measurement_id="contains spaces and secret=value")


def test_duplicate_outcome_must_be_non_billable():
    with pytest.raises(ShadowMeasurementValidationError):
        make_measurement(
            outcome=ShadowMeasurementOutcome.DUPLICATE,
            disposition=MaestroBillingDisposition.SETTLED,
        )


def test_custom_workload_requires_review():
    with pytest.raises(ShadowMeasurementValidationError):
        make_measurement(
            resource_band=MaestroResourceBand.CUSTOM,
            disposition=MaestroBillingDisposition.SETTLED,
        )


def test_measurement_is_frozen_and_serializes_decimals():
    measurement = make_measurement()

    with pytest.raises(FrozenInstanceError):
        measurement.execution_id = "changed"  # type: ignore[misc]

    record = measurement.to_dict()

    assert record["duration_ms"] == "125.5"
    assert record["estimated_total_cost"] == "0.03"
    assert record["quantities"]["base_executions"] == "1"
