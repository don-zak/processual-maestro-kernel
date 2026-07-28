from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from processual_api.billing.maestro_calibration_contracts import (
    CalibrationQuantities,
    MaestroBillingDisposition,
    MaestroFailureOwner,
    MaestroResourceBand,
    MaestroTaskFamily,
)

SHADOW_MEASUREMENT_VERSION = "maestro-unit-v1-calibration-r2a"
SHADOW_ONLY = True
APPROVED_FOR_QUOTA = False
APPROVED_FOR_INVOICING = False
APPROVED_FOR_CHECKOUT = False
APPROVED_FOR_RUNTIME_ENFORCEMENT = False

ZERO = Decimal(0)
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ShadowMeasurementValidationError(ValueError):
    """Raised when a shadow measurement violates a safety invariant."""


class ShadowMeasurementOutcome(StrEnum):
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DUPLICATE = "duplicate"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class MaestroShadowMeasurement:
    measurement_id: str
    execution_id: str
    attempt_id: str
    observed_at: datetime
    task_family: MaestroTaskFamily
    outcome: ShadowMeasurementOutcome
    quantities: CalibrationQuantities
    resource_band: MaestroResourceBand
    failure_owner: MaestroFailureOwner
    disposition: MaestroBillingDisposition
    duration_ms: Decimal
    estimated_provider_cost: Decimal = ZERO
    estimated_infrastructure_cost: Decimal = ZERO
    parent_execution_id: str | None = None
    workload_reference_id: str | None = None

    def __post_init__(self) -> None:
        _require_identifier("measurement_id", self.measurement_id)
        _require_identifier("execution_id", self.execution_id)
        _require_identifier("attempt_id", self.attempt_id)

        if self.parent_execution_id is not None:
            _require_identifier(
                "parent_execution_id",
                self.parent_execution_id,
            )

        if self.workload_reference_id is not None:
            _require_identifier(
                "workload_reference_id",
                self.workload_reference_id,
            )

        if not isinstance(self.observed_at, datetime):
            raise ShadowMeasurementValidationError("observed_at must be datetime")

        if self.observed_at.tzinfo is None:
            raise ShadowMeasurementValidationError("observed_at must be timezone-aware")

        if self.observed_at.utcoffset() != UTC.utcoffset(self.observed_at):
            raise ShadowMeasurementValidationError("observed_at must use UTC")

        if not isinstance(self.task_family, MaestroTaskFamily):
            raise ShadowMeasurementValidationError("task_family must be MaestroTaskFamily")

        if not isinstance(self.outcome, ShadowMeasurementOutcome):
            raise ShadowMeasurementValidationError("outcome must be ShadowMeasurementOutcome")

        if not isinstance(self.quantities, CalibrationQuantities):
            raise ShadowMeasurementValidationError("quantities must be CalibrationQuantities")

        if not isinstance(self.resource_band, MaestroResourceBand):
            raise ShadowMeasurementValidationError("resource_band must be MaestroResourceBand")

        if not isinstance(self.failure_owner, MaestroFailureOwner):
            raise ShadowMeasurementValidationError("failure_owner must be MaestroFailureOwner")

        if not isinstance(
            self.disposition,
            MaestroBillingDisposition,
        ):
            raise ShadowMeasurementValidationError("disposition must be MaestroBillingDisposition")

        _require_non_negative_decimal(
            "duration_ms",
            self.duration_ms,
        )
        _require_non_negative_decimal(
            "estimated_provider_cost",
            self.estimated_provider_cost,
        )
        _require_non_negative_decimal(
            "estimated_infrastructure_cost",
            self.estimated_infrastructure_cost,
        )

        if self.failure_owner is MaestroFailureOwner.PLATFORM and self.disposition is MaestroBillingDisposition.SETTLED:
            raise ShadowMeasurementValidationError("platform failures must not be settled")

        if (
            self.outcome is ShadowMeasurementOutcome.DUPLICATE
            and self.disposition is not MaestroBillingDisposition.NON_BILLABLE
        ):
            raise ShadowMeasurementValidationError("duplicate measurements must be non-billable")

        if (
            self.resource_band is MaestroResourceBand.CUSTOM
            and self.disposition is not MaestroBillingDisposition.REVIEW_REQUIRED
        ):
            raise ShadowMeasurementValidationError("custom workloads must require review")

    @property
    def estimated_total_cost(self) -> Decimal:
        return self.estimated_provider_cost + self.estimated_infrastructure_cost

    def to_dict(self) -> dict[str, Any]:
        return {
            "measurement_version": SHADOW_MEASUREMENT_VERSION,
            "shadow_only": SHADOW_ONLY,
            "measurement_id": self.measurement_id,
            "execution_id": self.execution_id,
            "attempt_id": self.attempt_id,
            "parent_execution_id": self.parent_execution_id,
            "workload_reference_id": self.workload_reference_id,
            "observed_at": self.observed_at.isoformat(),
            "task_family": self.task_family.value,
            "outcome": self.outcome.value,
            "quantities": {name: str(value) for name, value in asdict(self.quantities).items()},
            "resource_band": self.resource_band.value,
            "failure_owner": self.failure_owner.value,
            "disposition": self.disposition.value,
            "duration_ms": str(self.duration_ms),
            "estimated_provider_cost": str(self.estimated_provider_cost),
            "estimated_infrastructure_cost": str(self.estimated_infrastructure_cost),
            "estimated_total_cost": str(self.estimated_total_cost),
        }


def _require_identifier(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise ShadowMeasurementValidationError(f"{name} must be str")

    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ShadowMeasurementValidationError(f"{name} contains unsupported characters or length")


def _require_non_negative_decimal(
    name: str,
    value: object,
) -> None:
    if not isinstance(value, Decimal):
        raise ShadowMeasurementValidationError(f"{name} must be Decimal")

    try:
        if not value.is_finite():
            raise ShadowMeasurementValidationError(f"{name} must be finite")
    except InvalidOperation as exc:
        raise ShadowMeasurementValidationError(f"{name} must be a valid Decimal") from exc

    if value < ZERO:
        raise ShadowMeasurementValidationError(f"{name} must not be negative")
