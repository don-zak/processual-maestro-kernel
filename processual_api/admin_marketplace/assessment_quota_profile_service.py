from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Protocol, Self

from processual_api.admin_marketplace.assessment_quota_profile_persistence import (
    AdminMarketAssessmentQuotaProfile,
)
from processual_api.admin_marketplace.subscription_quota_profiles import (
    SubscriptionQuotaMetric,
    SubscriptionQuotaProfile,
    validate_quota_profile,
)
from processual_api.billing.assessment_activation_preparation import (
    ApprovedAssessmentOutcome,
    AssessmentActivationPreparationError,
    build_assessment_activation_profile,
)
from processual_api.billing.plan_fulfillment_catalog import QUOTA_METRIC_CODE

ASSESSMENT_QUOTA_PROFILE_VERSION: Final = "2026-08-assessment-quota-profile-v1"
ASSESSMENT_QUOTA_CYCLE_KIND: Final = "calendar_month"
MONTHLY_COMPATIBILITY_PERIOD_DAYS: Final = 30


class AssessmentQuotaProfileConflictError(RuntimeError):
    """A durable assessment quota binding conflicts with an existing definition."""


class AssessmentQuotaProfileIntegrityError(RuntimeError):
    """A durable assessment quota profile cannot be trusted for runtime use."""


class AssessmentQuotaProfileRepository(Protocol):
    async def get_by_profile_ref(
        self,
        profile_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentQuotaProfile | None: ...

    async def get_by_binding_hash(
        self,
        assessment_binding_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentQuotaProfile | None: ...

    def add(self, profile: AdminMarketAssessmentQuotaProfile) -> None: ...


class AssessmentQuotaProfileUnitOfWork(Protocol):
    assessment_quota_profiles: AssessmentQuotaProfileRepository

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
    async def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class AssessmentQuotaProfileResult:
    record: AdminMarketAssessmentQuotaProfile
    runtime_profile: SubscriptionQuotaProfile
    replayed: bool


def _payload_digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _runtime_profile(*, profile_ref: str, limit_units: int) -> SubscriptionQuotaProfile:
    return validate_quota_profile(
        SubscriptionQuotaProfile(
            profile_ref=profile_ref,
            period_days=MONTHLY_COMPATIBILITY_PERIOD_DAYS,
            metrics=(
                SubscriptionQuotaMetric(
                    metric_code=QUOTA_METRIC_CODE,
                    limit_units=limit_units,
                ),
            ),
        )
    )


def _definition_from_outcome(
    outcome: ApprovedAssessmentOutcome,
) -> tuple[dict[str, object], SubscriptionQuotaProfile]:
    activation = build_assessment_activation_profile(outcome)
    profile_ref = str(activation["quota_profile_ref"]).strip().lower()
    binding_hash = str(activation["assessment_binding_hash"]).strip().lower()
    approved_quota_units = activation["approved_quota_units"]
    entitlement_codes = activation["entitlement_codes"]
    approval = activation["approval"]
    if isinstance(approved_quota_units, bool) or not isinstance(
        approved_quota_units,
        int,
    ):
        raise ValueError("approved assessment quota must be an integer")
    if not isinstance(entitlement_codes, list) or not all(
        isinstance(code, str) for code in entitlement_codes
    ):
        raise ValueError("approved assessment entitlements are invalid")
    if not isinstance(approval, dict):
        raise ValueError("approved assessment approval metadata is invalid")

    definition: dict[str, object] = {
        "profile_ref": profile_ref,
        "assessment_binding_hash": binding_hash,
        "assessment_id": str(activation["assessment_id"]).strip(),
        "customer_ref": str(activation["customer_ref"]).strip().lower(),
        "public_plan_id": str(activation["public_plan_id"]).strip().lower(),
        "entitlement_source_plan_code": str(
            activation["entitlement_source_plan_code"]
        ).strip().lower(),
        "approved_by": str(approval["approved_by"]).strip(),
        "approval_reference": str(approval["approval_reference"]).strip(),
        "entitlement_codes_json": list(entitlement_codes),
        "metric_code": QUOTA_METRIC_CODE,
        "limit_units": approved_quota_units,
        "cycle_kind": ASSESSMENT_QUOTA_CYCLE_KIND,
        "compatibility_period_days": MONTHLY_COMPATIBILITY_PERIOD_DAYS,
        "definition_version": ASSESSMENT_QUOTA_PROFILE_VERSION,
    }
    definition["payload_digest"] = _payload_digest(definition)
    return definition, _runtime_profile(
        profile_ref=profile_ref,
        limit_units=approved_quota_units,
    )


async def ensure_assessment_quota_profile_in_unit(
    *,
    outcome: ApprovedAssessmentOutcome,
    unit: AssessmentQuotaProfileUnitOfWork,
) -> AssessmentQuotaProfileResult:
    try:
        definition, runtime_profile = _definition_from_outcome(outcome)
    except (AssessmentActivationPreparationError, ValueError) as exc:
        raise AssessmentQuotaProfileIntegrityError(str(exc)) from exc

    profile_ref = str(definition["profile_ref"])
    binding_hash = str(definition["assessment_binding_hash"])
    existing = await unit.assessment_quota_profiles.get_by_profile_ref(
        profile_ref,
        for_update=True,
    )
    if existing is None:
        existing = await unit.assessment_quota_profiles.get_by_binding_hash(
            binding_hash,
            for_update=True,
        )
    if existing is not None:
        expected_digest = str(definition["payload_digest"])
        if existing.payload_digest != expected_digest:
            raise AssessmentQuotaProfileConflictError(
                "assessment quota profile conflicts with durable state"
            )
        return AssessmentQuotaProfileResult(
            record=existing,
            runtime_profile=runtime_profile,
            replayed=True,
        )

    record = AdminMarketAssessmentQuotaProfile(
        profile_ref=profile_ref,
        assessment_binding_hash=binding_hash,
        assessment_id=str(definition["assessment_id"]),
        customer_ref=str(definition["customer_ref"]),
        public_plan_id=str(definition["public_plan_id"]),
        entitlement_source_plan_code=str(definition["entitlement_source_plan_code"]),
        approved_by=str(definition["approved_by"]),
        approval_reference=str(definition["approval_reference"]),
        entitlement_codes_json=list(definition["entitlement_codes_json"]),
        metric_code=str(definition["metric_code"]),
        limit_units=int(definition["limit_units"]),
        cycle_kind=str(definition["cycle_kind"]),
        compatibility_period_days=int(definition["compatibility_period_days"]),
        definition_version=str(definition["definition_version"]),
        payload_digest=str(definition["payload_digest"]),
    )
    unit.assessment_quota_profiles.add(record)
    return AssessmentQuotaProfileResult(
        record=record,
        runtime_profile=runtime_profile,
        replayed=False,
    )


def ensure_assessment_quota_profile_factory(
    *,
    unit_of_work_factory: Callable[[], AssessmentQuotaProfileUnitOfWork],
):
    async def ensure(
        *,
        outcome: ApprovedAssessmentOutcome,
    ) -> AssessmentQuotaProfileResult:
        async with unit_of_work_factory() as unit:
            result = await ensure_assessment_quota_profile_in_unit(
                outcome=outcome,
                unit=unit,
            )
            if not result.replayed:
                await unit.commit()
            return result

    return ensure


__all__ = [
    "ASSESSMENT_QUOTA_CYCLE_KIND",
    "ASSESSMENT_QUOTA_PROFILE_VERSION",
    "AssessmentQuotaProfileConflictError",
    "AssessmentQuotaProfileIntegrityError",
    "AssessmentQuotaProfileRepository",
    "AssessmentQuotaProfileResult",
    "AssessmentQuotaProfileUnitOfWork",
    "MONTHLY_COMPATIBILITY_PERIOD_DAYS",
    "ensure_assessment_quota_profile_factory",
    "ensure_assessment_quota_profile_in_unit",
]
