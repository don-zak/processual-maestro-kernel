from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

CALIBRATION_VERSION = "maestro-unit-v1-calibration-a"
SHADOW_ONLY = True
APPROVED_FOR_QUOTA = False
APPROVED_FOR_INVOICING = False
APPROVED_FOR_CHECKOUT = False

ZERO = Decimal(0)
ONE = Decimal(1)
MAX_RESOURCE_MODIFIER = Decimal("1.50")


class CalibrationValidationError(ValueError):
    """Raised when a calibration contract violates an invariant."""


class MaestroTaskFamily(StrEnum):
    AUTOMATION_EXECUTION = "automation_execution"
    INTEGRATION_OPERATION = "integration_operation"
    DOCUMENT_PROCESSING = "document_processing"
    DATA_TRANSFORMATION = "data_transformation"
    RESEARCH_SYNTHESIS = "research_synthesis"
    VERIFICATION_REVIEW = "verification_review"
    SUPERVISED_PROJECT = "supervised_project"


class MaestroBillingDisposition(StrEnum):
    SETTLED = "settled"
    NON_BILLABLE = "non_billable"
    RELEASED = "released"
    REVIEW_REQUIRED = "review_required"


class MaestroFailureOwner(StrEnum):
    NONE = "none"
    PLATFORM = "platform"
    CUSTOMER = "customer"
    EXTERNAL_PROVIDER = "external_provider"
    OPERATOR = "operator"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class MaestroResourceBand(StrEnum):
    NORMAL = "normal"
    HEAVY = "heavy"
    EXTREME = "extreme"
    CUSTOM = "custom"


RESOURCE_MODIFIERS: dict[MaestroResourceBand, Decimal | None] = {
    MaestroResourceBand.NORMAL: Decimal("1.00"),
    MaestroResourceBand.HEAVY: Decimal("1.25"),
    MaestroResourceBand.EXTREME: Decimal("1.50"),
    MaestroResourceBand.CUSTOM: None,
}


@dataclass(frozen=True, slots=True)
class CalibrationQuantities:
    base_executions: Decimal = ZERO
    integration_actions: Decimal = ZERO
    equivalent_pages: Decimal = ZERO
    records_processed: Decimal = ZERO
    verification_items: Decimal = ZERO
    standard_supervision_gates: Decimal = ZERO
    extended_supervision_gates: Decimal = ZERO
    excess_storage_gb_month: Decimal = ZERO

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            _require_decimal(name, value)
            _require_non_negative(name, value)


@dataclass(frozen=True, slots=True)
class CalibrationWorkload:
    workload_id: str
    title: str
    task_family: MaestroTaskFamily
    quantities: CalibrationQuantities
    resource_band: MaestroResourceBand
    expected_failure_owner: MaestroFailureOwner
    expected_disposition: MaestroBillingDisposition
    expected_raw_units: Decimal
    expected_settled_units: Decimal
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.workload_id or not self.workload_id.strip():
            raise CalibrationValidationError("workload_id must not be blank")
        if not self.title or not self.title.strip():
            raise CalibrationValidationError("title must not be blank")
        if not isinstance(self.task_family, MaestroTaskFamily):
            raise CalibrationValidationError("task_family must be MaestroTaskFamily")
        if not isinstance(self.quantities, CalibrationQuantities):
            raise CalibrationValidationError("quantities must be CalibrationQuantities")
        if not isinstance(self.resource_band, MaestroResourceBand):
            raise CalibrationValidationError("resource_band must be MaestroResourceBand")
        if not isinstance(self.expected_failure_owner, MaestroFailureOwner):
            raise CalibrationValidationError("expected_failure_owner must be MaestroFailureOwner")
        if not isinstance(self.expected_disposition, MaestroBillingDisposition):
            raise CalibrationValidationError("expected_disposition must be MaestroBillingDisposition")
        _require_decimal("expected_raw_units", self.expected_raw_units)
        _require_decimal("expected_settled_units", self.expected_settled_units)
        _require_non_negative("expected_raw_units", self.expected_raw_units)
        _require_non_negative("expected_settled_units", self.expected_settled_units)
        if self.expected_settled_units > self.expected_raw_units * MAX_RESOURCE_MODIFIER:
            raise CalibrationValidationError("settled units exceed maximum calibrated modifier")
        if self.expected_failure_owner is MaestroFailureOwner.PLATFORM and self.expected_settled_units != ZERO:
            raise CalibrationValidationError("platform failures must settle zero units")
        if self.expected_disposition is MaestroBillingDisposition.NON_BILLABLE and self.expected_settled_units != ZERO:
            raise CalibrationValidationError("non-billable workloads must settle zero units")
        if self.resource_band is MaestroResourceBand.CUSTOM and self.expected_settled_units != ZERO:
            raise CalibrationValidationError("custom workloads must not auto-settle in calibration v1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "workload_id": self.workload_id,
            "title": self.title,
            "task_family": self.task_family.value,
            "quantities": {key: str(value) for key, value in asdict(self.quantities).items()},
            "resource_band": self.resource_band.value,
            "expected_failure_owner": self.expected_failure_owner.value,
            "expected_disposition": self.expected_disposition.value,
            "expected_raw_units": str(self.expected_raw_units),
            "expected_settled_units": str(self.expected_settled_units),
            "notes": self.notes,
        }


def _require_decimal(name: str, value: object) -> None:
    if not isinstance(value, Decimal):
        raise CalibrationValidationError(f"{name} must be Decimal")
    try:
        if not value.is_finite():
            raise CalibrationValidationError(f"{name} must be finite")
    except InvalidOperation as exc:
        raise CalibrationValidationError(f"{name} must be a valid Decimal") from exc


def _require_non_negative(name: str, value: Decimal) -> None:
    if value < ZERO:
        raise CalibrationValidationError(f"{name} must not be negative")
