from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.assessment_commercial_read_service import (
    AssessmentCommercialReadIntegrityError,
    AssessmentSubscriptionCommercialReadService,
)
from processual_api.admin_marketplace.authority import authority_context


SUBSCRIPTION_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")
NOW = datetime(2026, 8, 9, 20, 0, tzinfo=UTC)
BINDING_HASH = "a" * 64


def _authority():
    return authority_context(
        user_id="platform-admin-1",
        session_id="session-1",
        platform_authorities={"platform_admin"},
        active_platform_admin=True,
        recent_mfa_step_up=False,
    )


def _activation(**overrides):
    values = {
        "subscription_id": SUBSCRIPTION_ID,
        "activation_ref": "act_assessment_read_001",
        "customer_ref": "institution-acme",
        "status": "activated",
        "activated_at": NOW,
        "created_at": NOW,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _subscription(**overrides):
    values = {
        "id": SUBSCRIPTION_ID,
        "subscription_ref": "sub_assessment_read_001",
        "customer_ref": "institution-acme",
        "status": "active",
        "starts_at": NOW,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _binding(**overrides):
    values = {
        "subscription_id": SUBSCRIPTION_ID,
        "assessment_binding_hash": BINDING_HASH,
        "assessment_id": "assessment-read-001",
        "customer_ref": "institution-acme",
        "public_plan_id": "academic_institution",
        "entitlement_source_plan_code": "academic",
        "entitlement_profile_ref": "academic-entitlements-v1",
        "quota_profile_ref": "assessment_quota_aaaaaaaaaaaaaaaaaaaaaaaa",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _quota(**overrides):
    values = {
        "profile_ref": "assessment_quota_aaaaaaaaaaaaaaaaaaaaaaaa",
        "assessment_binding_hash": BINDING_HASH,
        "assessment_id": "assessment-read-001",
        "customer_ref": "institution-acme",
        "public_plan_id": "academic_institution",
        "entitlement_source_plan_code": "academic",
        "metric_code": "credits",
        "limit_units": 125_000,
        "cycle_kind": "calendar_month",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _terms(**overrides):
    values = {
        "terms_ref": "assessment_terms_aaaaaaaaaaaaaaaaaaaaaaaa",
        "assessment_binding_hash": BINDING_HASH,
        "assessment_id": "assessment-read-001",
        "customer_ref": "institution-acme",
        "public_plan_id": "academic_institution",
        "price_source": "contract",
        "source_reference": "institution-contract-2026-001",
        "currency": "USD",
        "billing_interval": "annual",
        "amount_minor_units": 240_000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _ListRepository:
    def __init__(self, items) -> None:
        self.items = list(items)

    async def list_recent(self, *, limit=100):
        return self.items[:limit]


class _SubscriptionRepository:
    def __init__(self, subscription) -> None:
        self.subscription = subscription

    async def get_by_id(self, subscription_id, *, for_update=False):
        if self.subscription is not None and self.subscription.id == subscription_id:
            return self.subscription
        return None


class _BindingRepository:
    def __init__(self, binding) -> None:
        self.binding = binding

    async def get_by_subscription_id(self, subscription_id, *, for_update=False):
        if self.binding is not None and self.binding.subscription_id == subscription_id:
            return self.binding
        return None


class _QuotaRepository:
    def __init__(self, quota) -> None:
        self.quota = quota

    async def get_by_profile_ref(self, profile_ref, *, for_update=False):
        if self.quota is not None and self.quota.profile_ref == profile_ref:
            return self.quota
        return None


class _TermsRepository:
    def __init__(self, terms) -> None:
        self.terms = terms

    async def get_by_binding_hash(self, binding_hash, *, for_update=False):
        if self.terms is not None and self.terms.assessment_binding_hash == binding_hash:
            return self.terms
        return None


class _Unit:
    def __init__(
        self,
        *,
        activations=None,
        subscription=None,
        binding=None,
        quota=None,
        terms=None,
    ) -> None:
        self.entitlement_activations = _ListRepository(activations or [_activation()])
        self.subscriptions = _SubscriptionRepository(subscription or _subscription())
        self.assessment_subscription_bindings = _BindingRepository(
            _binding() if binding is None else binding
        )
        self.assessment_quota_profiles = _QuotaRepository(_quota() if quota is None else quota)
        self.assessment_commercial_terms = _TermsRepository(
            _terms() if terms is None else terms
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


@pytest.mark.asyncio
async def test_assessment_read_exposes_authoritative_quota_and_terms_without_order_payment() -> None:
    unit = _Unit()
    service = AssessmentSubscriptionCommercialReadService(
        unit_of_work_factory=lambda: unit,
    )

    rows = await service.list_assessment_subscriptions(authority=_authority())

    assert len(rows) == 1
    row = rows[0]
    assert row.public_plan_id == "academic_institution"
    assert row.entitlement_source_plan_code == "academic"
    assert row.quota_metric_code == "credits"
    assert row.quota_limit_units == 125_000
    assert row.quota_cycle_kind == "calendar_month"
    assert row.price_source == "contract"
    assert row.price_source_reference == "institution-contract-2026-001"
    assert row.currency == "USD"
    assert row.billing_interval == "annual"
    assert row.amount_minor_units == 240_000
    assert not hasattr(row, "order_ref")
    assert not hasattr(row, "payment_status")
    assert not hasattr(row, "offer_ref")


@pytest.mark.asyncio
async def test_assessment_read_fails_closed_when_terms_are_missing() -> None:
    unit = _Unit(terms=False)
    unit.assessment_commercial_terms = _TermsRepository(None)
    service = AssessmentSubscriptionCommercialReadService(
        unit_of_work_factory=lambda: unit,
    )

    with pytest.raises(AssessmentCommercialReadIntegrityError, match="incomplete"):
        await service.list_assessment_subscriptions(authority=_authority())


@pytest.mark.asyncio
async def test_assessment_read_rejects_tampered_binding() -> None:
    unit = _Unit(terms=_terms(amount_minor_units=240_000))
    unit.assessment_commercial_terms = _TermsRepository(
        _terms(customer_ref="different-customer")
    )
    service = AssessmentSubscriptionCommercialReadService(
        unit_of_work_factory=lambda: unit,
    )

    with pytest.raises(AssessmentCommercialReadIntegrityError, match="inconsistent"):
        await service.list_assessment_subscriptions(authority=_authority())


@pytest.mark.asyncio
async def test_direct_order_activation_is_not_misclassified_as_assessment() -> None:
    unit = _Unit(binding=False)
    unit.assessment_subscription_bindings = _BindingRepository(None)
    service = AssessmentSubscriptionCommercialReadService(
        unit_of_work_factory=lambda: unit,
    )

    rows = await service.list_assessment_subscriptions(authority=_authority())

    assert rows == ()
