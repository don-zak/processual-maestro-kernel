from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Self

from processual_api.admin_marketplace.assessment_commercial_terms_persistence import (
    AdminMarketAssessmentCommercialTerms,
)
from processual_api.admin_marketplace.assessment_commercial_terms_service import (
    ApprovedAssessmentCommercialTerms,
    ensure_assessment_commercial_terms_in_unit,
)
from processual_api.admin_marketplace.assessment_quota_profile_service import (
    AssessmentQuotaProfileRepository,
    ensure_assessment_quota_profile_in_unit,
)
from processual_api.admin_marketplace.assessment_subscription_persistence import (
    AdminMarketAssessmentSubscriptionBinding,
)
from processual_api.admin_marketplace.audit_contracts import (
    CommercialAuditAction,
    CommercialAuditOutcome,
    CommercialAuditRecord,
    CommercialResourceType,
)
from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
    AdminMarketEntitlementActivation,
    AdminMarketPlan,
    AdminMarketSubscription,
)
from processual_api.admin_marketplace.subscription_runtime_bootstrap import (
    SubscriptionQuotaRepository,
    SubscriptionRuntimeBootstrapInput,
    SubscriptionRuntimeRepository,
    bootstrap_subscription_runtime_in_unit,
)
from processual_api.billing.assessment_activation_preparation import (
    ApprovedAssessmentOutcome,
)


class AssessmentSubscriptionActivationError(RuntimeError):
    """An approved assessment cannot be converted into a subscription safely."""


class AssessmentSubscriptionActivationConflictError(
    AssessmentSubscriptionActivationError
):
    """Assessment activation conflicts with durable subscription state."""


class _PlanRepository(Protocol):
    async def get_by_id(
        self,
        plan_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketPlan | None: ...


class _SubscriptionRepository(Protocol):
    async def get_by_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscription | None: ...

    async def get_active_by_customer_ref(
        self,
        customer_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscription | None: ...

    def add(self, subscription: AdminMarketSubscription) -> None: ...


class _EntitlementActivationRepository(Protocol):
    def add(self, activation: AdminMarketEntitlementActivation) -> None: ...


class _AssessmentSubscriptionBindingRepository(Protocol):
    async def get_by_subscription_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentSubscriptionBinding | None: ...

    async def get_by_assessment_binding_hash(
        self,
        assessment_binding_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentSubscriptionBinding | None: ...

    async def get_by_idempotency_key_hash(
        self,
        key_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentSubscriptionBinding | None: ...

    def add(self, binding: AdminMarketAssessmentSubscriptionBinding) -> None: ...


class _CommercialAuditRepository(Protocol):
    def append(self, audit_record: AdminMarketAuditRecord) -> None: ...


class _AssessmentCommercialTermsRepository(Protocol):
    async def get_by_binding_hash(
        self,
        assessment_binding_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentCommercialTerms | None: ...

    async def get_by_approval_reference(
        self,
        approval_reference: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentCommercialTerms | None: ...

    def add(self, terms: AdminMarketAssessmentCommercialTerms) -> None: ...


class AssessmentSubscriptionActivationUnitOfWork(Protocol):
    assessment_quota_profiles: AssessmentQuotaProfileRepository
    assessment_commercial_terms: _AssessmentCommercialTermsRepository
    subscription_runtime: SubscriptionRuntimeRepository
    subscription_quotas: SubscriptionQuotaRepository
    plans: _PlanRepository
    subscriptions: _SubscriptionRepository
    entitlement_activations: _EntitlementActivationRepository
    assessment_subscription_bindings: _AssessmentSubscriptionBindingRepository
    commercial_audit: _CommercialAuditRepository

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
    async def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class AssessmentSubscriptionActivationResult:
    subscription_id: uuid.UUID
    subscription_ref: str
    binding_ref: str
    customer_ref: str
    public_plan_id: str
    entitlement_source_plan_code: str
    quota_profile_ref: str
    commercial_terms_ref: str
    activated_at: datetime
    replayed: bool


def _required(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise AssessmentSubscriptionActivationError(f"{name} is required")
    return normalized


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _state_digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return _sha256(canonical)


def _result(
    *,
    subscription: AdminMarketSubscription,
    binding: AdminMarketAssessmentSubscriptionBinding,
    commercial_terms_ref: str,
    replayed: bool,
) -> AssessmentSubscriptionActivationResult:
    activated_at = subscription.starts_at or subscription.created_at
    return AssessmentSubscriptionActivationResult(
        subscription_id=subscription.id,
        subscription_ref=subscription.subscription_ref,
        binding_ref=binding.binding_ref,
        customer_ref=binding.customer_ref,
        public_plan_id=binding.public_plan_id,
        entitlement_source_plan_code=binding.entitlement_source_plan_code,
        quota_profile_ref=binding.quota_profile_ref,
        commercial_terms_ref=commercial_terms_ref,
        activated_at=activated_at,
        replayed=replayed,
    )


def _binding_matches(
    binding: AdminMarketAssessmentSubscriptionBinding,
    *,
    assessment_binding_hash: str,
    customer_ref: str,
    public_plan_id: str,
    entitlement_source_plan_code: str,
    entitlement_plan_id: uuid.UUID,
    entitlement_profile_ref: str,
    quota_profile_ref: str,
) -> bool:
    return (
        binding.assessment_binding_hash == assessment_binding_hash
        and binding.customer_ref == customer_ref
        and binding.public_plan_id == public_plan_id
        and binding.entitlement_source_plan_code == entitlement_source_plan_code
        and binding.entitlement_plan_id == entitlement_plan_id
        and binding.entitlement_profile_ref == entitlement_profile_ref
        and binding.quota_profile_ref == quota_profile_ref
    )


async def _load_replay(
    *,
    unit: AssessmentSubscriptionActivationUnitOfWork,
    binding: AdminMarketAssessmentSubscriptionBinding,
    assessment_binding_hash: str,
    customer_ref: str,
    public_plan_id: str,
    entitlement_source_plan_code: str,
    entitlement_plan_id: uuid.UUID,
    entitlement_profile_ref: str,
    quota_profile_ref: str,
    commercial_terms_ref: str,
) -> AssessmentSubscriptionActivationResult:
    if not _binding_matches(
        binding,
        assessment_binding_hash=assessment_binding_hash,
        customer_ref=customer_ref,
        public_plan_id=public_plan_id,
        entitlement_source_plan_code=entitlement_source_plan_code,
        entitlement_plan_id=entitlement_plan_id,
        entitlement_profile_ref=entitlement_profile_ref,
        quota_profile_ref=quota_profile_ref,
    ):
        raise AssessmentSubscriptionActivationConflictError(
            "assessment activation binding conflicts with the requested durable state"
        )
    subscription = await unit.subscriptions.get_by_id(
        binding.subscription_id,
        for_update=True,
    )
    if (
        subscription is None
        or subscription.customer_ref != customer_ref
        or subscription.plan_id != entitlement_plan_id
        or subscription.status != "active"
    ):
        raise AssessmentSubscriptionActivationConflictError(
            "assessment activation binding references an invalid subscription"
        )
    return _result(
        subscription=subscription,
        binding=binding,
        commercial_terms_ref=commercial_terms_ref,
        replayed=True,
    )


class AssessmentSubscriptionActivationService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AssessmentSubscriptionActivationUnitOfWork],
        clock: Callable[[], datetime],
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        event_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._id_factory = id_factory
        self._event_id_factory = event_id_factory

    async def activate(
        self,
        *,
        outcome: ApprovedAssessmentOutcome,
        commercial_terms: ApprovedAssessmentCommercialTerms,
        entitlement_plan_id: uuid.UUID,
        correlation_id: str,
        idempotency_key: str,
    ) -> AssessmentSubscriptionActivationResult:
        correlation_id = _required(correlation_id, "correlation_id")
        idempotency_hash = _sha256(_required(idempotency_key, "idempotency_key"))
        now = self._clock()
        if now.tzinfo is None:
            raise AssessmentSubscriptionActivationError(
                "assessment activation clock must be timezone-aware"
            )

        async with self._unit_of_work_factory() as unit:
            quota = await ensure_assessment_quota_profile_in_unit(
                outcome=outcome,
                unit=unit,
            )
            record = quota.record
            commercial = await ensure_assessment_commercial_terms_in_unit(
                outcome=outcome,
                terms=commercial_terms,
                unit=unit,
            )
            terms_record = commercial.record
            if terms_record.assessment_binding_hash != record.assessment_binding_hash:
                raise AssessmentSubscriptionActivationConflictError(
                    "commercial terms are not bound to the assessment activation"
                )

            customer_ref = record.customer_ref
            assessment_binding_hash = record.assessment_binding_hash
            public_plan_id = record.public_plan_id
            source_plan_code = record.entitlement_source_plan_code

            plan = await unit.plans.get_by_id(entitlement_plan_id, for_update=True)
            if (
                plan is None
                or plan.plan_code.strip().lower() != source_plan_code
                or not plan.entitlement_profile_ref.strip()
            ):
                raise AssessmentSubscriptionActivationError(
                    "authoritative entitlement source plan does not match the assessment binding"
                )
            entitlement_profile_ref = plan.entitlement_profile_ref.strip().lower()

            by_idempotency = (
                await unit.assessment_subscription_bindings.get_by_idempotency_key_hash(
                    idempotency_hash,
                    for_update=True,
                )
            )
            if by_idempotency is not None:
                return await _load_replay(
                    unit=unit,
                    binding=by_idempotency,
                    assessment_binding_hash=assessment_binding_hash,
                    customer_ref=customer_ref,
                    public_plan_id=public_plan_id,
                    entitlement_source_plan_code=source_plan_code,
                    entitlement_plan_id=plan.id,
                    entitlement_profile_ref=entitlement_profile_ref,
                    quota_profile_ref=record.profile_ref,
                    commercial_terms_ref=terms_record.terms_ref,
                )

            by_assessment = await unit.assessment_subscription_bindings.get_by_assessment_binding_hash(
                assessment_binding_hash,
                for_update=True,
            )
            if by_assessment is not None:
                return await _load_replay(
                    unit=unit,
                    binding=by_assessment,
                    assessment_binding_hash=assessment_binding_hash,
                    customer_ref=customer_ref,
                    public_plan_id=public_plan_id,
                    entitlement_source_plan_code=source_plan_code,
                    entitlement_plan_id=plan.id,
                    entitlement_profile_ref=entitlement_profile_ref,
                    quota_profile_ref=record.profile_ref,
                    commercial_terms_ref=terms_record.terms_ref,
                )

            active = await unit.subscriptions.get_active_by_customer_ref(
                customer_ref,
                for_update=True,
            )
            if active is not None:
                existing_binding = (
                    await unit.assessment_subscription_bindings.get_by_subscription_id(
                        active.id,
                        for_update=True,
                    )
                )
                if existing_binding is not None:
                    return await _load_replay(
                        unit=unit,
                        binding=existing_binding,
                        assessment_binding_hash=assessment_binding_hash,
                        customer_ref=customer_ref,
                        public_plan_id=public_plan_id,
                        entitlement_source_plan_code=source_plan_code,
                        entitlement_plan_id=plan.id,
                        entitlement_profile_ref=entitlement_profile_ref,
                        quota_profile_ref=record.profile_ref,
                        commercial_terms_ref=terms_record.terms_ref,
                    )
                raise AssessmentSubscriptionActivationConflictError(
                    "customer already has an active subscription from another activation source"
                )

            ref_suffix = assessment_binding_hash[:24]
            subscription = AdminMarketSubscription(
                id=self._id_factory(),
                subscription_ref=f"sub_assessment_{ref_suffix}",
                customer_ref=customer_ref,
                order_id=None,
                offer_id=None,
                plan_id=plan.id,
                status="active",
                starts_at=now,
                ends_at=None,
                created_at=now,
                updated_at=now,
            )
            activation = AdminMarketEntitlementActivation(
                id=self._id_factory(),
                activation_ref=f"act_assessment_{ref_suffix}",
                customer_ref=customer_ref,
                order_id=None,
                subscription_id=subscription.id,
                entitlement_profile_ref=entitlement_profile_ref,
                automatic_activation_allowed=False,
                status="activated",
                activation_idempotency_key_hash=idempotency_hash,
                activated_at=now,
                created_at=now,
            )
            binding = AdminMarketAssessmentSubscriptionBinding(
                id=self._id_factory(),
                binding_ref=f"asb_{ref_suffix}",
                subscription_id=subscription.id,
                assessment_binding_hash=assessment_binding_hash,
                assessment_id=record.assessment_id,
                customer_ref=customer_ref,
                public_plan_id=public_plan_id,
                entitlement_source_plan_code=source_plan_code,
                entitlement_plan_id=plan.id,
                entitlement_profile_ref=entitlement_profile_ref,
                quota_profile_ref=record.profile_ref,
                activation_idempotency_key_hash=idempotency_hash,
                created_at=now,
            )

            unit.subscriptions.add(subscription)
            unit.entitlement_activations.add(activation)
            unit.assessment_subscription_bindings.add(binding)
            await bootstrap_subscription_runtime_in_unit(
                source=SubscriptionRuntimeBootstrapInput(
                    subscription_id=subscription.id,
                    customer_ref=customer_ref,
                    entitlement_profile_ref=entitlement_profile_ref,
                    quota_profile_ref=record.profile_ref,
                    subscription_status=subscription.status,
                    effective_at=now,
                ),
                quota_profile=quota.runtime_profile,
                uow=unit,
            )

            state = {
                "subscription_ref": subscription.subscription_ref,
                "binding_ref": binding.binding_ref,
                "assessment_binding_hash": assessment_binding_hash,
                "customer_ref": customer_ref,
                "public_plan_id": public_plan_id,
                "entitlement_source_plan_code": source_plan_code,
                "entitlement_profile_ref": entitlement_profile_ref,
                "quota_profile_ref": record.profile_ref,
                "commercial_terms_ref": terms_record.terms_ref,
                "price_source": terms_record.price_source,
                "price_source_reference": terms_record.source_reference,
                "currency": terms_record.currency,
                "billing_interval": terms_record.billing_interval,
                "amount_minor_units": terms_record.amount_minor_units,
            }
            audit = CommercialAuditRecord(
                event_id=str(self._event_id_factory()),
                occurred_at=now,
                actor_user_id="system_assessment_activation",
                actor_session_id="system",
                platform_authority="system",
                action=CommercialAuditAction.SUBSCRIPTION_ACTIVATION_DECIDED,
                resource_type=CommercialResourceType.SUBSCRIPTION,
                resource_id=subscription.subscription_ref,
                outcome=CommercialAuditOutcome.ALLOWED,
                reason_code="assessment_subscription_activated",
                correlation_id=correlation_id,
                previous_state_digest=None,
                new_state_digest=_state_digest(state),
                metadata={
                    "assessment_id": record.assessment_id,
                    "public_plan_id": public_plan_id,
                    "entitlement_source_plan_code": source_plan_code,
                    "quota_profile_ref": record.profile_ref,
                    "commercial_terms_ref": terms_record.terms_ref,
                    "price_source": terms_record.price_source,
                    "price_source_reference": terms_record.source_reference,
                    "binding_ref": binding.binding_ref,
                },
            )
            unit.commercial_audit.append(
                AdminMarketAuditRecord(
                    id=uuid.UUID(audit.event_id),
                    event_ref=audit.event_id,
                    occurred_at=audit.occurred_at,
                    actor_user_id=audit.actor_user_id,
                    actor_session_id=audit.actor_session_id,
                    platform_authority=audit.platform_authority,
                    action=audit.action.value,
                    resource_type=audit.resource_type.value,
                    resource_id=audit.resource_id,
                    outcome=audit.outcome.value,
                    reason_code=audit.reason_code,
                    correlation_id=audit.correlation_id,
                    previous_state_digest=audit.previous_state_digest,
                    new_state_digest=audit.new_state_digest,
                    metadata_json=dict(audit.metadata),
                    created_at=audit.occurred_at,
                )
            )
            await unit.commit()
            return _result(
                subscription=subscription,
                binding=binding,
                commercial_terms_ref=terms_record.terms_ref,
                replayed=False,
            )


__all__ = [
    "AssessmentSubscriptionActivationConflictError",
    "AssessmentSubscriptionActivationError",
    "AssessmentSubscriptionActivationResult",
    "AssessmentSubscriptionActivationService",
    "AssessmentSubscriptionActivationUnitOfWork",
]
