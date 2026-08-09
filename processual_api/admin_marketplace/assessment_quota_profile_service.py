from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Protocol

from processual_api.admin_marketplace.assessment_quota_profile_persistence import (
    AdminMarketAssessmentQuotaProfile,
)
from processual_api.admin_marketplace.subscription_quota_profiles import (
    SubscriptionQuotaMetric,
    SubscriptionQuotaProfile,
)
from processual_api.billing.assessment_activation_preparation import (
    ApprovedAssessmentOutcome,
    build_assessment_activation_profile,
)
from processual_api.billing.plan_fulfillment_catalog import QUOTA_METRIC_CODE

ASSESSMENT_QUOTA_PROFILE_VERSION: Final = "2026-08-assessment-quota-profile-v1"
ASSESSMENT_QUOTA_CYCLE_KIND: Final = "calendar_month"
MONTHLY_COMPATIBILITY_PERIOD_DAYS: Final = 30


class AssessmentQuotaProfileConflictError(RuntimeError):
    """A durable assessment quota binding conflicts with an existing definition."""


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

    async def __aenter__(self) -> AssessmentQuotaProfileUnitOfWork: ...
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


def _definition_from_outcome(
    outcome: ApprovedAssessmentOutcome,
) -> tuple[dict[str, object], SubscriptionQuotaProfile]:
    activation = build_assessment_activation_profile(outcome)
    profile_ref = str(activation["quota_profile_ref"]).strip().lower()
    binding_hash = str(activation["assessment_binding_hash"]).strip().lower()
    approved_quota_units = activation["approved_quota_units"]
    if isinstance(approved_quota_units, bool) or not isinstance(
        approved_quota_units,
        int,
    ):
        raise ValueError("approved assessment quota must be an integer")

    definition: dict[str, object] = {
        "profile_ref": profile_ref,
        "assessment_binding_hash": binding_hash,
        "assessment_id": str(activation["assessment_id"]).strip(),
        "customer_ref": str(activation["customer_ref"]).strip().lower(),
        "public_plan_id": str(activation["public_plan_id"]).strip().lower(),
        "entitlement_source_plan_code": str(
            activation["entitlement_source_plan_code"]
        ).strip().lower(),
        "metric_code": QUOTA_METRIC_CODE,
        "limit_units": approved_quota_units,
        "cycle_kind": ASSESSMENT_QUOTA_CYCLE_KIND,
        "compatibility_period_days": MONTHLY_COMPATIBILITY_PERIOD_DAYS,
        "definition_version": ASSESSMENT_QUOTA_PROFILE_VERSION,
    }
    definition["payload_digest"] = _payload_digest(definition)

    runtime_profile = SubscriptionQuotaProfile(
        profile_ref=profile_ref,
        period_days=MONTHLY_COMPATIBILITY_PERIOD_DAYS,
        metrics=(
            SubscriptionQuotaMetric(
                metric_code=QUOTA_METRIC_CODE,
                limit_units=approved_quota_units,
            ),
        ),
    )
    return definition, runtime_profile


def _record_matches(
    record: AdminMarketAssessmentQuotaProfile,
    definition: dict[str, object],
) -> bool:
    return all(
        getattr(record, field) == value
        for field, value in definition.items()
    )


def ensure_assessment_quota_profile_factory(
    *,
    unit_of_work_factory: Callable[[], AssessmentQuotaProfileUnitOfWork],
):
    async def ensure(
        outcome: ApprovedAssessmentOutcome,
    ) -> AssessmentQuotaProfileResult:
        definition, runtime_profile = _definition_from_outcome(outcome)
        profile_ref = str(definition["profile_ref"])
        binding_hash = str(definition["assessment_binding_hash"])

        async with unit_of_work_factory() as unit:
            existing = await unit.assessment_quota_profiles.get_by_profile_ref(
                profile_ref,
                for_update=True,
            )
            if existing is not None:
                if not _record_matches(existing, definition):
                    raise AssessmentQuotaProfileConflictError(
                        "assessment quota profile reference conflicts with its durable definition."
                    )
                return AssessmentQuotaProfileResult(
                    record=existing,
                    runtime_profile=runtime_profile,
                    replayed=True,
                )

            binding_existing = await unit.assessment_quota_profiles.get_by_binding_hash(
                binding_hash,
                for_update=True,
            )
            if binding_existing is not None:
                raise AssessmentQuotaProfileConflictError(
                    "assessment quota binding already exists under a different profile reference."
                )

            record = AdminMarketAssessmentQuotaProfile(**definition)
            unit.assessment_quota_profiles.add(record)
            await unit.commit()
            return AssessmentQuotaProfileResult(
                record=record,
                runtime_profile=runtime_profile,
                replayed=False,
            )

    return ensure


__all__ = [
    "ASSESSMENT_QUOTA_CYCLE_KIND",
    "ASSESSMENT_QUOTA_PROFILE_VERSION",
    "MONTHLY_COMPATIBILITY_PERIOD_DAYS",
    "AssessmentQuotaProfileConflictError",
    "AssessmentQuotaProfileResult",
    "ensure_assessment_quota_profile_factory",
]
