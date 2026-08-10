from __future__ import annotations

from datetime import UTC, datetime

import pytest

from processual_api.admin_marketplace.assessment_commercial_terms_persistence import (
    AdminMarketAssessmentCommercialTerms,
)
from processual_api.admin_marketplace.assessment_commercial_terms_service import (
    ApprovedAssessmentCommercialTerms,
    AssessmentCommercialTermsConflictError,
    AssessmentCommercialTermsError,
    ensure_assessment_commercial_terms_factory,
    ensure_assessment_commercial_terms_in_unit,
)
from processual_api.admin_marketplace.assessment_quota_profile_persistence import (
    AdminMarketAssessmentQuotaProfile,
)
from processual_api.billing.assessment_activation_preparation import ApprovedAssessmentOutcome
from processual_api.billing.assessment_plan_fulfillment import assessment_plan_entitlements


def _outcome(**overrides) -> ApprovedAssessmentOutcome:
    values = {
        "assessment_id": "assessment_academic_terms_001",
        "customer_ref": "Institution-ACME",
        "public_plan_id": "academic_institution",
        "approval_status": "approved",
        "approved_quota_units": 125_000,
        "approved_entitlement_codes": assessment_plan_entitlements("academic_institution"),
        "approved_by": "assessment-reviewer",
        "approval_reference": "assessment-approval-001",
    }
    values.update(overrides)
    return ApprovedAssessmentOutcome(**values)


def _terms(**overrides) -> ApprovedAssessmentCommercialTerms:
    values = {
        "price_source": "contract",
        "source_reference": "institution-contract-2026-001",
        "currency": "USD",
        "billing_interval": "annual",
        "amount_minor_units": 240_000,
        "approved_by": "commercial-reviewer",
        "approval_reference": "commercial-approval-001",
        "effective_at": datetime(2026, 8, 9, 18, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return ApprovedAssessmentCommercialTerms(**values)


class _QuotaRepository:
    def __init__(self) -> None:
        self.records: dict[str, AdminMarketAssessmentQuotaProfile] = {}

    async def get_by_profile_ref(self, profile_ref: str, *, for_update: bool = False):
        return self.records.get(profile_ref)

    async def get_by_binding_hash(self, assessment_binding_hash: str, *, for_update: bool = False):
        return next(
            (item for item in self.records.values() if item.assessment_binding_hash == assessment_binding_hash),
            None,
        )

    def add(self, profile: AdminMarketAssessmentQuotaProfile) -> None:
        self.records[profile.profile_ref] = profile


class _TermsRepository:
    def __init__(self) -> None:
        self.records: dict[str, AdminMarketAssessmentCommercialTerms] = {}

    async def get_by_binding_hash(self, assessment_binding_hash: str, *, for_update: bool = False):
        return next(
            (item for item in self.records.values() if item.assessment_binding_hash == assessment_binding_hash),
            None,
        )

    async def get_by_approval_reference(self, approval_reference: str, *, for_update: bool = False):
        return next(
            (item for item in self.records.values() if item.approval_reference == approval_reference),
            None,
        )

    def add(self, terms: AdminMarketAssessmentCommercialTerms) -> None:
        self.records[terms.terms_ref] = terms


class _Unit:
    def __init__(self) -> None:
        self.assessment_quota_profiles = _QuotaRepository()
        self.assessment_commercial_terms = _TermsRepository()
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.mark.asyncio
async def test_contract_price_terms_bind_to_assessment_without_offer_order_or_payment() -> None:
    unit = _Unit()
    ensure = ensure_assessment_commercial_terms_factory(lambda: unit)

    result = await ensure(outcome=_outcome(), terms=_terms())

    assert result.replayed is False
    assert result.record.public_plan_id == "academic_institution"
    assert result.record.price_source == "contract"
    assert result.record.source_reference == "institution-contract-2026-001"
    assert result.record.currency == "USD"
    assert result.record.billing_interval == "annual"
    assert result.record.amount_minor_units == 240_000
    assert result.record.assessment_binding_hash
    assert result.record.terms_ref.startswith("assessment_terms_")
    assert unit.commit_count == 1


@pytest.mark.asyncio
async def test_in_unit_terms_creation_defers_commit_to_outer_transaction() -> None:
    unit = _Unit()

    result = await ensure_assessment_commercial_terms_in_unit(
        outcome=_outcome(),
        terms=_terms(price_source="assessment", source_reference="assessment-pricing-001"),
        unit=unit,
    )

    assert result.replayed is False
    assert result.record.price_source == "assessment"
    assert unit.commit_count == 0


@pytest.mark.asyncio
async def test_identical_terms_replay_without_second_commit() -> None:
    unit = _Unit()
    ensure = ensure_assessment_commercial_terms_factory(lambda: unit)

    first = await ensure(outcome=_outcome(), terms=_terms())
    second = await ensure(outcome=_outcome(), terms=_terms())

    assert second.replayed is True
    assert second.record.terms_ref == first.record.terms_ref
    assert second.record.payload_digest == first.record.payload_digest
    assert unit.commit_count == 1


@pytest.mark.asyncio
async def test_changed_amount_for_same_assessment_binding_fails_closed() -> None:
    unit = _Unit()
    ensure = ensure_assessment_commercial_terms_factory(lambda: unit)

    await ensure(outcome=_outcome(), terms=_terms())

    with pytest.raises(AssessmentCommercialTermsConflictError):
        await ensure(outcome=_outcome(), terms=_terms(amount_minor_units=1))

    assert unit.commit_count == 1


@pytest.mark.asyncio
async def test_academic_individual_price_cannot_be_inferred_through_invalid_source() -> None:
    unit = _Unit()
    ensure = ensure_assessment_commercial_terms_factory(lambda: unit)

    with pytest.raises(AssessmentCommercialTermsError, match="price_source"):
        await ensure(
            outcome=_outcome(),
            terms=_terms(price_source="catalog", source_reference="academic"),
        )

    assert unit.commit_count == 0
    assert unit.assessment_commercial_terms.records == {}


@pytest.mark.asyncio
async def test_missing_or_naive_authoritative_terms_fail_closed() -> None:
    unit = _Unit()
    ensure = ensure_assessment_commercial_terms_factory(lambda: unit)

    with pytest.raises(AssessmentCommercialTermsError):
        await ensure(outcome=_outcome(), terms=_terms(source_reference=""))

    with pytest.raises(AssessmentCommercialTermsError, match="timezone-aware"):
        await ensure(
            outcome=_outcome(),
            terms=_terms(effective_at=datetime(2026, 8, 9, 18, 0)),
        )

    assert unit.commit_count == 0
