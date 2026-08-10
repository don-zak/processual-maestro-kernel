from __future__ import annotations

import pytest

from processual_api.admin_marketplace.assessment_quota_profile_persistence import (
    AdminMarketAssessmentQuotaProfile,
)
from processual_api.admin_marketplace.assessment_quota_profile_service import (
    ASSESSMENT_QUOTA_CYCLE_KIND,
    MONTHLY_COMPATIBILITY_PERIOD_DAYS,
    AssessmentQuotaProfileConflictError,
    AssessmentQuotaProfileIntegrityError,
    ensure_assessment_quota_profile_factory,
    ensure_assessment_quota_profile_in_unit,
    resolve_assessment_quota_profile_factory,
)
from processual_api.billing.assessment_activation_preparation import (
    ApprovedAssessmentOutcome,
    build_assessment_activation_profile,
)
from processual_api.billing.assessment_plan_fulfillment import (
    assessment_plan_entitlements,
)
from processual_api.billing.plan_fulfillment_catalog import QUOTA_METRIC_CODE


def _outcome(**overrides) -> ApprovedAssessmentOutcome:
    values = {
        "assessment_id": "assessment_academic_001",
        "customer_ref": "Institution-ACME",
        "public_plan_id": "academic_institution",
        "approval_status": "approved",
        "approved_quota_units": 125_000,
        "approved_entitlement_codes": assessment_plan_entitlements(
            "academic_institution"
        ),
        "approved_by": "commercial-reviewer",
        "approval_reference": "approval-2026-08-001",
    }
    values.update(overrides)
    return ApprovedAssessmentOutcome(**values)


class _FakeRepository:
    def __init__(self) -> None:
        self.records: dict[str, AdminMarketAssessmentQuotaProfile] = {}

    async def get_by_profile_ref(
        self,
        profile_ref: str,
        *,
        for_update: bool = False,
    ):
        return self.records.get(profile_ref)

    async def get_by_binding_hash(
        self,
        assessment_binding_hash: str,
        *,
        for_update: bool = False,
    ):
        return next(
            (
                item
                for item in self.records.values()
                if item.assessment_binding_hash == assessment_binding_hash
            ),
            None,
        )

    def add(self, profile: AdminMarketAssessmentQuotaProfile) -> None:
        self.records[profile.profile_ref] = profile


class _FakeUnitOfWork:
    def __init__(self, repository: _FakeRepository) -> None:
        self.assessment_quota_profiles = repository
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.mark.asyncio
async def test_assessment_quota_profile_uses_exact_approved_quota_and_canonical_metric() -> None:
    repository = _FakeRepository()
    unit = _FakeUnitOfWork(repository)
    ensure = ensure_assessment_quota_profile_factory(unit_of_work_factory=lambda: unit)

    result = await ensure(_outcome())

    assert result.replayed is False
    assert result.record.public_plan_id == "academic_institution"
    assert result.record.entitlement_source_plan_code == "academic"
    assert result.record.limit_units == 125_000
    assert result.record.limit_units != 5_000
    assert result.record.metric_code == QUOTA_METRIC_CODE == "credits"
    assert result.record.cycle_kind == ASSESSMENT_QUOTA_CYCLE_KIND == "calendar_month"
    assert (
        result.record.compatibility_period_days
        == MONTHLY_COMPATIBILITY_PERIOD_DAYS
        == 30
    )
    assert result.runtime_profile.profile_ref == result.record.profile_ref
    assert result.runtime_profile.period_days == 30
    assert result.runtime_profile.metrics[0].metric_code == "credits"
    assert result.runtime_profile.metrics[0].limit_units == 125_000
    assert unit.commit_count == 1


@pytest.mark.asyncio
async def test_assessment_quota_profile_in_unit_defers_commit_to_outer_transaction() -> None:
    repository = _FakeRepository()
    unit = _FakeUnitOfWork(repository)

    result = await ensure_assessment_quota_profile_in_unit(
        outcome=_outcome(),
        unit=unit,
    )

    assert result.replayed is False
    assert result.record.profile_ref in repository.records
    assert unit.commit_count == 0


@pytest.mark.asyncio
async def test_same_assessment_binding_replays_same_durable_profile() -> None:
    repository = _FakeRepository()
    unit = _FakeUnitOfWork(repository)
    ensure = ensure_assessment_quota_profile_factory(unit_of_work_factory=lambda: unit)

    first = await ensure(_outcome())
    second = await ensure(_outcome())

    assert first.record.profile_ref == second.record.profile_ref
    assert first.record.payload_digest == second.record.payload_digest
    assert second.replayed is True
    assert unit.commit_count == 1


@pytest.mark.asyncio
async def test_changed_approved_quota_creates_new_binding_and_profile() -> None:
    repository = _FakeRepository()
    unit = _FakeUnitOfWork(repository)
    ensure = ensure_assessment_quota_profile_factory(unit_of_work_factory=lambda: unit)

    first = await ensure(_outcome())
    changed = await ensure(_outcome(approved_quota_units=200_000))

    assert first.record.assessment_binding_hash != changed.record.assessment_binding_hash
    assert first.record.profile_ref != changed.record.profile_ref
    assert first.record.limit_units == 125_000
    assert changed.record.limit_units == 200_000
    assert unit.commit_count == 2


@pytest.mark.asyncio
async def test_same_profile_ref_with_different_payload_fails_closed() -> None:
    repository = _FakeRepository()
    unit = _FakeUnitOfWork(repository)
    ensure = ensure_assessment_quota_profile_factory(unit_of_work_factory=lambda: unit)

    first = await ensure(_outcome())
    repository.records[first.record.profile_ref] = AdminMarketAssessmentQuotaProfile(
        profile_ref=first.record.profile_ref,
        assessment_binding_hash=first.record.assessment_binding_hash,
        assessment_id=first.record.assessment_id,
        customer_ref=first.record.customer_ref,
        public_plan_id=first.record.public_plan_id,
        entitlement_source_plan_code=first.record.entitlement_source_plan_code,
        approved_by=first.record.approved_by,
        approval_reference=first.record.approval_reference,
        entitlement_codes_json=list(first.record.entitlement_codes_json),
        metric_code=first.record.metric_code,
        limit_units=5_000,
        cycle_kind=first.record.cycle_kind,
        compatibility_period_days=first.record.compatibility_period_days,
        definition_version=first.record.definition_version,
        payload_digest=first.record.payload_digest,
    )

    with pytest.raises(AssessmentQuotaProfileConflictError):
        await ensure(_outcome())

    assert unit.commit_count == 1


@pytest.mark.asyncio
async def test_binding_hash_under_different_profile_ref_fails_closed() -> None:
    repository = _FakeRepository()
    unit = _FakeUnitOfWork(repository)
    ensure = ensure_assessment_quota_profile_factory(unit_of_work_factory=lambda: unit)
    outcome = _outcome()
    activation = build_assessment_activation_profile(outcome)

    repository.records["assessment_quota_conflicting_ref"] = (
        AdminMarketAssessmentQuotaProfile(
            profile_ref="assessment_quota_conflicting_ref",
            assessment_binding_hash=str(activation["assessment_binding_hash"]),
            assessment_id=outcome.assessment_id,
            customer_ref=outcome.customer_ref.lower(),
            public_plan_id=outcome.public_plan_id,
            entitlement_source_plan_code="academic",
            approved_by=outcome.approved_by,
            approval_reference=outcome.approval_reference,
            entitlement_codes_json=list(outcome.approved_entitlement_codes),
            metric_code="credits",
            limit_units=outcome.approved_quota_units,
            cycle_kind="calendar_month",
            compatibility_period_days=30,
            definition_version="2026-08-assessment-quota-profile-v1",
            payload_digest="0" * 64,
        )
    )

    with pytest.raises(AssessmentQuotaProfileConflictError):
        await ensure(outcome)

    assert unit.commit_count == 0


@pytest.mark.asyncio
async def test_durable_profile_resolves_to_exact_runtime_quota() -> None:
    repository = _FakeRepository()
    unit = _FakeUnitOfWork(repository)
    ensure = ensure_assessment_quota_profile_factory(unit_of_work_factory=lambda: unit)
    resolve = resolve_assessment_quota_profile_factory(unit_of_work_factory=lambda: unit)

    created = await ensure(_outcome())
    resolved = await resolve(created.record.profile_ref)

    assert resolved.profile_ref == created.record.profile_ref
    assert resolved.period_days == 30
    assert resolved.metrics[0].metric_code == "credits"
    assert resolved.metrics[0].limit_units == 125_000


@pytest.mark.asyncio
async def test_durable_profile_tampering_fails_closed_on_resolution() -> None:
    repository = _FakeRepository()
    unit = _FakeUnitOfWork(repository)
    ensure = ensure_assessment_quota_profile_factory(unit_of_work_factory=lambda: unit)
    resolve = resolve_assessment_quota_profile_factory(unit_of_work_factory=lambda: unit)

    created = await ensure(_outcome())
    created.record.limit_units = 5_000

    with pytest.raises(AssessmentQuotaProfileIntegrityError):
        await resolve(created.record.profile_ref)


@pytest.mark.asyncio
async def test_missing_durable_profile_fails_closed_on_resolution() -> None:
    repository = _FakeRepository()
    unit = _FakeUnitOfWork(repository)
    resolve = resolve_assessment_quota_profile_factory(unit_of_work_factory=lambda: unit)

    with pytest.raises(AssessmentQuotaProfileIntegrityError):
        await resolve("assessment_quota_missing")
