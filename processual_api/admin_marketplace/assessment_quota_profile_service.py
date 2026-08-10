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


def _record_payload(record: AdminMarketAssessmentQuotaProfile) -> dict[str, object]:
    return {
        "profile_ref": record.profile_ref,
        "assessment_binding_hash": record.assessment_binding_hash,
        "assessment_id": record.assessment_id,
        "customer_ref": record.customer_ref,
        "public_plan_id": record.public_plan_id,
        "entitlement_source_plan_code": record.entitlement_source_plan_code,
        "approved_by": record.approved_by,
        "approval_reference": record.approval_reference,
        "entitlement_codes_json": list(record.entitlement_codes_json),
        "metric_code": record.metric_code,
        "limit_units": record.limit_units,
        "cycle_kind": record.cycle_kind,
        "compatibility_period_days": record.compatibility_period_days,
        "definition_version": record.definition_version,
    }


def _record_matches(
    record: AdminMarketAssessmentQuotaProfile,
    definition: dict[str, object],
) -> bool:
    return all(getattr(record, field) == value for field, value in definition.items())


def _verify_assessment_binding(record: AdminMarketAssessmentQuotaProfile) -> None:
    try:
        rebuilt = build_assessment_activation_profile(
            ApprovedAssessmentOutcome(
                assessment_id=record.assessment_id,
                customer_ref=record.customer_ref,
                public_plan_id=record.public_plan_id,
                approval_status="approved",
                approved_quota_units=record.limit_units,
                approved_entitlement_codes=tuple(record.entitlement_codes_json),
                approved_by=record.approved_by,
                approval_reference=record.approval_reference,
            )
        )
    except (AssessmentActivationPreparationError, KeyError, TypeError, ValueError) as exc:
        raise AssessmentQuotaProfileIntegrityError(
            "assessment quota profile cannot reproduce an authoritative approved assessment."
        ) from exc

    if (
        rebuilt["assessment_binding_hash"] != record.assessment_binding_hash
        or rebuilt["quota_profile_ref"] != record.profile_ref
        or rebuilt["public_plan_id"] != record.public_plan_id
        or rebuilt["entitlement_source_plan_code"]
        != record.entitlement_source_plan_code
    ):
        raise AssessmentQuotaProfileIntegrityError(
            "assessment quota profile binding does not match the authoritative assessment template."
        )


def _trusted_runtime_profile(
    record: AdminMarketAssessmentQuotaProfile,
) -> SubscriptionQuotaProfile:
    try:
        payload = _record_payload(record)
    except (TypeError, ValueError) as exc:
        raise AssessmentQuotaProfileIntegrityError(
            "assessment quota profile payload is malformed."
        ) from exc
    expected_digest = _payload_digest(payload)
    if record.payload_digest != expected_digest:
        raise AssessmentQuotaProfileIntegrityError(
            "assessment quota profile payload digest does not match its durable definition."
        )
    if record.metric_code != QUOTA_METRIC_CODE:
        raise AssessmentQuotaProfileIntegrityError(
            "assessment quota profile metric is not authoritative."
        )
    if record.cycle_kind != ASSESSMENT_QUOTA_CYCLE_KIND:
        raise AssessmentQuotaProfileIntegrityError(
            "assessment quota profile cycle is not calendar-month anchored."
        )
    if record.compatibility_period_days != MONTHLY_COMPATIBILITY_PERIOD_DAYS:
        raise AssessmentQuotaProfileIntegrityError(
            "assessment quota profile monthly compatibility marker is invalid."
        )
    if record.definition_version != ASSESSMENT_QUOTA_PROFILE_VERSION:
        raise AssessmentQuotaProfileIntegrityError(
            "assessment quota profile definition version is not supported."
        )
    if (
        isinstance(record.limit_units, bool)
        or not isinstance(record.limit_units, int)
        or record.limit_units <= 0
    ):
        raise AssessmentQuotaProfileIntegrityError(
            "assessment quota profile limit is invalid."
        )
    _verify_assessment_binding(record)
    return _runtime_profile(
        profile_ref=record.profile_ref,
        limit_units=record.limit_units,
    )


async def ensure_assessment_quota_profile_in_unit(
    *,
    outcome: ApprovedAssessmentOutcome,
    unit: AssessmentQuotaProfileUnitOfWork,
) -> AssessmentQuotaProfileResult:
    """Ensure an assessment quota profile without owning the transaction boundary."""

    definition, runtime_profile = _definition_from_outcome(outcome)
    profile_ref = str(definition["profile_ref"])
    binding_hash = str(definition["assessment_binding_hash"])

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
            runtime_profile=_trusted_runtime_profile(existing),
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
    return AssessmentQuotaProfileResult(
        record=record,
        runtime_profile=runtime_profile,
        replayed=False,
    )


async def resolve_assessment_quota_profile_in_unit(
    *,
    profile_ref: str,
    unit: AssessmentQuotaProfileUnitOfWork,
) -> SubscriptionQuotaProfile:
    """Resolve a trusted assessment quota profile inside an existing transaction."""

    normalized_ref = profile_ref.strip().lower()
    if not normalized_ref:
        raise AssessmentQuotaProfileIntegrityError(
            "assessment quota profile reference is required."
        )
    record = await unit.assessment_quota_profiles.get_by_profile_ref(
        normalized_ref,
        for_update=False,
    )
    if record is None:
        raise AssessmentQuotaProfileIntegrityError(
            "assessment quota profile was not found."
        )
    if record.profile_ref != normalized_ref:
        raise AssessmentQuotaProfileIntegrityError(
            "assessment quota profile reference is not canonical."
        )
    return _trusted_runtime_profile(record)


def ensure_assessment_quota_profile_factory(
    *,
    unit_of_work_factory: Callable[[], AssessmentQuotaProfileUnitOfWork],
):
    async def ensure(
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


def resolve_assessment_quota_profile_factory(
    *,
    unit_of_work_factory: Callable[[], AssessmentQuotaProfileUnitOfWork],
):
    async def resolve(profile_ref: str) -> SubscriptionQuotaProfile:
        async with unit_of_work_factory() as unit:
            return await resolve_assessment_quota_profile_in_unit(
                profile_ref=profile_ref,
                unit=unit,
            )

    return resolve


__all__ = [
    "ASSESSMENT_QUOTA_CYCLE_KIND",
    "ASSESSMENT_QUOTA_PROFILE_VERSION",
    "MONTHLY_COMPATIBILITY_PERIOD_DAYS",
    "AssessmentQuotaProfileConflictError",
    "AssessmentQuotaProfileIntegrityError",
    "AssessmentQuotaProfileResult",
    "ensure_assessment_quota_profile_factory",
    "ensure_assessment_quota_profile_in_unit",
    "resolve_assessment_quota_profile_factory",
    "resolve_assessment_quota_profile_in_unit",
]
