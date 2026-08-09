from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from processual_api.admin_marketplace.assessment_commercial_terms_persistence import (
    AdminMarketAssessmentCommercialTerms,
)
from processual_api.admin_marketplace.assessment_quota_profile_persistence import (
    AdminMarketAssessmentQuotaProfile,
)
from processual_api.admin_marketplace.assessment_subscription_persistence import (
    AdminMarketAssessmentSubscriptionBinding,
)
from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAction,
    AdminMarketplaceAuthorityContext,
    require_admin_marketplace_authority,
)
from processual_api.admin_marketplace.models import (
    AdminMarketEntitlementActivation,
    AdminMarketSubscription,
)


class AssessmentCommercialReadIntegrityError(RuntimeError):
    """Assessment commercial read state is incomplete or internally inconsistent."""


class _EntitlementActivationRepository(Protocol):
    async def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> Sequence[AdminMarketEntitlementActivation]: ...


class _SubscriptionRepository(Protocol):
    async def get_by_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscription | None: ...


class _AssessmentSubscriptionBindingRepository(Protocol):
    async def get_by_subscription_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentSubscriptionBinding | None: ...


class _AssessmentQuotaProfileRepository(Protocol):
    async def get_by_profile_ref(
        self,
        profile_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentQuotaProfile | None: ...


class _AssessmentCommercialTermsRepository(Protocol):
    async def get_by_binding_hash(
        self,
        assessment_binding_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentCommercialTerms | None: ...


class AssessmentCommercialReadUnitOfWork(Protocol):
    entitlement_activations: _EntitlementActivationRepository
    subscriptions: _SubscriptionRepository
    assessment_subscription_bindings: _AssessmentSubscriptionBindingRepository
    assessment_quota_profiles: _AssessmentQuotaProfileRepository
    assessment_commercial_terms: _AssessmentCommercialTermsRepository

    async def __aenter__(self) -> AssessmentCommercialReadUnitOfWork: ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...


@dataclass(frozen=True, slots=True)
class AssessmentSubscriptionCommercialReadResult:
    activation_ref: str
    subscription_ref: str
    assessment_id: str
    customer_ref: str
    public_plan_id: str
    entitlement_source_plan_code: str
    entitlement_profile_ref: str
    quota_profile_ref: str
    quota_metric_code: str
    quota_limit_units: int
    quota_cycle_kind: str
    commercial_terms_ref: str
    price_source: str
    price_source_reference: str
    currency: str
    billing_interval: str
    amount_minor_units: int
    subscription_status: str
    activation_status: str
    starts_at: datetime | None
    activated_at: datetime


def _validate_binding(
    *,
    activation: AdminMarketEntitlementActivation,
    subscription: AdminMarketSubscription,
    binding: AdminMarketAssessmentSubscriptionBinding,
    quota: AdminMarketAssessmentQuotaProfile,
    terms: AdminMarketAssessmentCommercialTerms,
) -> None:
    if (
        binding.subscription_id != subscription.id
        or activation.subscription_id != subscription.id
        or activation.customer_ref != binding.customer_ref
        or subscription.customer_ref != binding.customer_ref
        or quota.profile_ref != binding.quota_profile_ref
        or quota.assessment_binding_hash != binding.assessment_binding_hash
        or terms.assessment_binding_hash != binding.assessment_binding_hash
        or quota.assessment_id != binding.assessment_id
        or terms.assessment_id != binding.assessment_id
        or quota.customer_ref != binding.customer_ref
        or terms.customer_ref != binding.customer_ref
        or quota.public_plan_id != binding.public_plan_id
        or terms.public_plan_id != binding.public_plan_id
        or quota.entitlement_source_plan_code
        != binding.entitlement_source_plan_code
    ):
        raise AssessmentCommercialReadIntegrityError(
            "assessment subscription commercial binding is inconsistent"
        )
    if quota.metric_code != "credits" or quota.limit_units <= 0:
        raise AssessmentCommercialReadIntegrityError(
            "assessment quota profile is not safe for commercial read"
        )
    if terms.price_source not in {"assessment", "contract"}:
        raise AssessmentCommercialReadIntegrityError(
            "assessment price source is not authoritative"
        )


class AssessmentSubscriptionCommercialReadService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AssessmentCommercialReadUnitOfWork],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def list_assessment_subscriptions(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        limit: int = 100,
    ) -> tuple[AssessmentSubscriptionCommercialReadResult, ...]:
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.VIEW_CATALOG,
        )
        async with self._unit_of_work_factory() as unit:
            activations = await unit.entitlement_activations.list_recent(limit=limit)
            rows: list[AssessmentSubscriptionCommercialReadResult] = []
            for activation in activations:
                binding = await unit.assessment_subscription_bindings.get_by_subscription_id(
                    activation.subscription_id
                )
                if binding is None:
                    continue
                subscription = await unit.subscriptions.get_by_id(activation.subscription_id)
                quota = await unit.assessment_quota_profiles.get_by_profile_ref(
                    binding.quota_profile_ref
                )
                terms = await unit.assessment_commercial_terms.get_by_binding_hash(
                    binding.assessment_binding_hash
                )
                if subscription is None or quota is None or terms is None:
                    raise AssessmentCommercialReadIntegrityError(
                        "assessment subscription commercial state is incomplete"
                    )
                _validate_binding(
                    activation=activation,
                    subscription=subscription,
                    binding=binding,
                    quota=quota,
                    terms=terms,
                )
                rows.append(
                    AssessmentSubscriptionCommercialReadResult(
                        activation_ref=activation.activation_ref,
                        subscription_ref=subscription.subscription_ref,
                        assessment_id=binding.assessment_id,
                        customer_ref=binding.customer_ref,
                        public_plan_id=binding.public_plan_id,
                        entitlement_source_plan_code=(
                            binding.entitlement_source_plan_code
                        ),
                        entitlement_profile_ref=binding.entitlement_profile_ref,
                        quota_profile_ref=binding.quota_profile_ref,
                        quota_metric_code=quota.metric_code,
                        quota_limit_units=quota.limit_units,
                        quota_cycle_kind=quota.cycle_kind,
                        commercial_terms_ref=terms.terms_ref,
                        price_source=terms.price_source,
                        price_source_reference=terms.source_reference,
                        currency=terms.currency,
                        billing_interval=terms.billing_interval,
                        amount_minor_units=terms.amount_minor_units,
                        subscription_status=subscription.status,
                        activation_status=activation.status,
                        starts_at=subscription.starts_at,
                        activated_at=activation.activated_at or activation.created_at,
                    )
                )
        return tuple(rows)


__all__ = [
    "AssessmentCommercialReadIntegrityError",
    "AssessmentCommercialReadUnitOfWork",
    "AssessmentSubscriptionCommercialReadResult",
    "AssessmentSubscriptionCommercialReadService",
]
