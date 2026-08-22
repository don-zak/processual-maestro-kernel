from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.assessment_commercial_terms_service import (
    ApprovedAssessmentCommercialTerms,
    AssessmentCommercialTermsError,
)
from processual_api.admin_marketplace.assessment_subscription_activation_service import (
    AssessmentSubscriptionActivationError,
    AssessmentSubscriptionActivationService,
)
from processual_api.admin_marketplace.subscription_quota_usage import (
    SubscriptionQuotaUsageCommand,
    SubscriptionQuotaUsageError,
    record_subscription_quota_usage_factory,
)
from processual_api.billing.assessment_activation_preparation import (
    ApprovedAssessmentOutcome,
)
from processual_api.billing.assessment_plan_fulfillment import (
    assessment_plan_entitlements,
)


class _AssessmentQuotaRepository:
    def __init__(self) -> None:
        self.records = {}

    async def get_by_profile_ref(self, profile_ref, *, for_update=False):
        return self.records.get(profile_ref)

    async def get_by_binding_hash(self, binding_hash, *, for_update=False):
        return next(
            (
                record
                for record in self.records.values()
                if record.assessment_binding_hash == binding_hash
            ),
            None,
        )

    def add(self, record) -> None:
        self.records[record.profile_ref] = record


class _CommercialTermsRepository:
    def __init__(self) -> None:
        self.records = {}

    async def get_by_binding_hash(self, binding_hash, *, for_update=False):
        return next(
            (
                record
                for record in self.records.values()
                if record.assessment_binding_hash == binding_hash
            ),
            None,
        )

    async def get_by_approval_reference(
        self,
        approval_reference,
        *,
        for_update=False,
    ):
        return next(
            (
                record
                for record in self.records.values()
                if record.approval_reference == approval_reference
            ),
            None,
        )

    def add(self, record) -> None:
        self.records[record.terms_ref] = record


class _PlanRepository:
    def __init__(self, plan) -> None:
        self.plan = plan

    async def get_by_id(self, plan_id, *, for_update=False):
        if self.plan is not None and self.plan.id == plan_id:
            return self.plan
        return None


class _SubscriptionRepository:
    def __init__(self) -> None:
        self.by_id = {}

    async def get_by_id(self, subscription_id, *, for_update=False):
        return self.by_id.get(subscription_id)

    async def get_active_by_customer_ref(self, customer_ref, *, for_update=False):
        return next(
            (
                item
                for item in self.by_id.values()
                if item.customer_ref == customer_ref and item.status == "active"
            ),
            None,
        )

    def add(self, subscription) -> None:
        self.by_id[subscription.id] = subscription


class _ActivationRepository:
    def __init__(self) -> None:
        self.added = []

    def add(self, activation) -> None:
        self.added.append(activation)


class _BindingRepository:
    def __init__(self) -> None:
        self.by_subscription = {}

    async def get_by_subscription_id(self, subscription_id, *, for_update=False):
        return self.by_subscription.get(subscription_id)

    async def get_by_assessment_binding_hash(self, binding_hash, *, for_update=False):
        return next(
            (
                item
                for item in self.by_subscription.values()
                if item.assessment_binding_hash == binding_hash
            ),
            None,
        )

    async def get_by_idempotency_key_hash(self, key_hash, *, for_update=False):
        return next(
            (
                item
                for item in self.by_subscription.values()
                if item.activation_idempotency_key_hash == key_hash
            ),
            None,
        )

    def add(self, binding) -> None:
        self.by_subscription[binding.subscription_id] = binding


class _RuntimeRepository:
    def __init__(self) -> None:
        self.by_subscription = {}

    async def get_by_subscription_id(self, subscription_id, *, for_update=False):
        return self.by_subscription.get(subscription_id)

    def add(self, runtime) -> None:
        self.by_subscription[runtime.subscription_id] = runtime


class _QuotaCycleRepository:
    def __init__(self) -> None:
        self.added = []

    async def get_current(
        self,
        *,
        subscription_id,
        metric_code,
        occurred_at,
        for_update=False,
    ):
        return next(
            (
                item
                for item in self.added
                if item.subscription_id == subscription_id
                and item.metric_code == metric_code
                and item.period_start <= occurred_at < item.period_end
            ),
            None,
        )

    async def get_by_id(self, cycle_id, *, for_update=False):
        return next((item for item in self.added if item.id == cycle_id), None)

    def add(self, cycle) -> None:
        if cycle.id is None:
            cycle.id = uuid.uuid4()
        self.added.append(cycle)


class _QuotaCycleUsageRepository:
    def __init__(self) -> None:
        self.by_hash = {}
        self.added = []

    async def get_by_idempotency_hash(self, key_hash, *, for_update=False):
        return self.by_hash.get(key_hash)

    async def sum_units_since(self, *, quota_cycle_id, occurred_at):
        return sum(
            item.units
            for item in self.added
            if item.quota_cycle_id == quota_cycle_id
            and item.occurred_at >= occurred_at
        )

    def add(self, usage) -> None:
        self.added.append(usage)
        self.by_hash[usage.idempotency_key_hash] = usage


class _AuditRepository:
    def __init__(self) -> None:
        self.added = []

    def append(self, record) -> None:
        self.added.append(record)


class _UnitOfWork:
    def __init__(self, plan) -> None:
        self.assessment_quota_profiles = _AssessmentQuotaRepository()
        self.assessment_commercial_terms = _CommercialTermsRepository()
        self.plans = _PlanRepository(plan)
        self.subscriptions = _SubscriptionRepository()
        self.entitlement_activations = _ActivationRepository()
        self.assessment_subscription_bindings = _BindingRepository()
        self.subscription_runtime = _RuntimeRepository()
        self.subscription_quota_cycles = _QuotaCycleRepository()
        self.subscription_quota_cycle_usage = _QuotaCycleUsageRepository()
        self.subscription_delinquency = SimpleNamespace()
        self.commercial_audit = _AuditRepository()
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


def _outcome() -> ApprovedAssessmentOutcome:
    return ApprovedAssessmentOutcome(
        assessment_id="assessment-academic-001",
        customer_ref="Institution-ACME",
        public_plan_id="academic_institution",
        approval_status="approved",
        approved_quota_units=125_000,
        approved_entitlement_codes=assessment_plan_entitlements(
            "academic_institution"
        ),
        approved_by="commercial-reviewer",
        approval_reference="approval-2026-08-001",
    )


def _commercial_terms(**overrides) -> ApprovedAssessmentCommercialTerms:
    values = {
        "price_source": "contract",
        "source_reference": "institution-contract-2026-001",
        "currency": "USD",
        "billing_interval": "annual",
        "amount_minor_units": 240_000,
        "approved_by": "commercial-reviewer",
        "approval_reference": "commercial-approval-2026-08-001",
        "effective_at": datetime(2026, 8, 9, 19, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return ApprovedAssessmentCommercialTerms(**values)


def _plan(*, plan_code: str = "academic"):
    return SimpleNamespace(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        plan_code=plan_code,
        entitlement_profile_ref="academic-entitlements-v1",
        quota_profile_ref="academic-default-5k",
    )


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_assessment_activation_is_atomic_and_uses_exact_assessment_quota() -> None:
    plan = _plan()
    unit = _UnitOfWork(plan)
    now = datetime(2026, 8, 9, 20, 0, tzinfo=UTC)
    ids = iter(
        (
            uuid.UUID("20000000-0000-0000-0000-000000000001"),
            uuid.UUID("20000000-0000-0000-0000-000000000002"),
            uuid.UUID("20000000-0000-0000-0000-000000000003"),
        )
    )
    service = AssessmentSubscriptionActivationService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: now,
        id_factory=lambda: next(ids),
        event_id_factory=lambda: uuid.UUID(
            "30000000-0000-0000-0000-000000000001"
        ),
    )

    result = await service.activate(
        outcome=_outcome(),
        commercial_terms=_commercial_terms(),
        entitlement_plan_id=plan.id,
        correlation_id="corr-assessment-001",
        idempotency_key="idem-assessment-001",
    )

    subscription = unit.subscriptions.by_id[result.subscription_id]
    binding = unit.assessment_subscription_bindings.by_subscription[result.subscription_id]
    terms = next(iter(unit.assessment_commercial_terms.records.values()))
    assert result.replayed is False
    assert unit.commit_count == 1
    assert subscription.order_id is None
    assert subscription.offer_id is None
    assert subscription.plan_id == plan.id
    assert binding.public_plan_id == "academic_institution"
    assert binding.entitlement_source_plan_code == "academic"
    assert binding.quota_profile_ref.startswith("assessment_quota_")
    assert binding.quota_profile_ref != plan.quota_profile_ref
    assert result.commercial_terms_ref == terms.terms_ref
    assert terms.price_source == "contract"
    assert terms.source_reference == "institution-contract-2026-001"
    assert terms.amount_minor_units == 240_000
    assert len(unit.subscription_quota_cycles.added) == 1
    cycle = unit.subscription_quota_cycles.added[0]
    assert cycle.metric_code == "maestro_units"
    assert cycle.base_limit_units == 125_000
    assert cycle.base_limit_units != 5_000
    assert cycle.quota_profile_ref == binding.quota_profile_ref
    assert cycle.plan_code == "academic"
    assert cycle.plan_catalog_version == "2026-08-assessment-quota-profile-v1"
    assert len(unit.entitlement_activations.added) == 1
    assert unit.entitlement_activations.added[0].order_id is None
    assert unit.entitlement_activations.added[0].automatic_activation_allowed is False
    assert len(unit.commercial_audit.added) == 1
    assert unit.commercial_audit.added[0].metadata_json["commercial_terms_ref"] == terms.terms_ref


@pytest.mark.asyncio
async def test_assessment_subscription_runtime_enforces_exact_quota_via_authoritative_cycle() -> None:
    plan = _plan()
    unit = _UnitOfWork(plan)
    now = datetime(2026, 8, 9, 20, 0, tzinfo=UTC)
    activation_service = AssessmentSubscriptionActivationService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: now,
    )
    activation = await activation_service.activate(
        outcome=_outcome(),
        commercial_terms=_commercial_terms(),
        entitlement_plan_id=plan.id,
        correlation_id="corr-assessment-runtime",
        idempotency_key="idem-assessment-runtime",
    )
    record_usage = record_subscription_quota_usage_factory(
        unit_of_work_factory=lambda: unit
    )

    await record_usage(
        SubscriptionQuotaUsageCommand(
            subscription_id=activation.subscription_id,
            customer_ref=activation.customer_ref,
            metric_code="maestro_units",
            units=125_000,
            idempotency_key_hash=_hash("usage-exact-limit"),
            dimensions_digest=_hash("assessment-e2e"),
            occurred_at=now,
        )
    )

    cycle = unit.subscription_quota_cycles.added[0]
    assert cycle.base_limit_units == 125_000
    assert cycle.used_units == 125_000

    with pytest.raises(SubscriptionQuotaUsageError, match="insufficient"):
        await record_usage(
            SubscriptionQuotaUsageCommand(
                subscription_id=activation.subscription_id,
                customer_ref=activation.customer_ref,
                metric_code="maestro_units",
                units=1,
                idempotency_key_hash=_hash("usage-over-limit"),
                dimensions_digest=_hash("assessment-e2e-over"),
                occurred_at=now,
            )
        )

    assert cycle.used_units == 125_000
    assert len(unit.subscription_quota_cycle_usage.added) == 1


@pytest.mark.asyncio
async def test_same_assessment_replays_without_second_subscription_cycle_or_commit() -> None:
    plan = _plan()
    unit = _UnitOfWork(plan)
    now = datetime(2026, 8, 9, 20, 0, tzinfo=UTC)
    service = AssessmentSubscriptionActivationService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: now,
    )

    first = await service.activate(
        outcome=_outcome(),
        commercial_terms=_commercial_terms(),
        entitlement_plan_id=plan.id,
        correlation_id="corr-assessment-001",
        idempotency_key="idem-assessment-001",
    )
    replay = await service.activate(
        outcome=_outcome(),
        commercial_terms=_commercial_terms(),
        entitlement_plan_id=plan.id,
        correlation_id="corr-assessment-002",
        idempotency_key="idem-assessment-001",
    )

    assert replay.replayed is True
    assert replay.subscription_id == first.subscription_id
    assert replay.binding_ref == first.binding_ref
    assert replay.commercial_terms_ref == first.commercial_terms_ref
    assert len(unit.subscriptions.by_id) == 1
    assert len(unit.assessment_commercial_terms.records) == 1
    assert len(unit.subscription_quota_cycles.added) == 1
    assert unit.commit_count == 1


@pytest.mark.asyncio
async def test_assessment_activation_rejects_wrong_entitlement_source_plan() -> None:
    plan = _plan(plan_code="starter")
    unit = _UnitOfWork(plan)
    service = AssessmentSubscriptionActivationService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: datetime(2026, 8, 9, 20, 0, tzinfo=UTC),
    )

    with pytest.raises(AssessmentSubscriptionActivationError):
        await service.activate(
            outcome=_outcome(),
            commercial_terms=_commercial_terms(),
            entitlement_plan_id=plan.id,
            correlation_id="corr-assessment-001",
            idempotency_key="idem-assessment-001",
        )

    assert unit.commit_count == 0
    assert unit.subscriptions.by_id == {}
    assert unit.subscription_runtime.by_subscription == {}
    assert unit.subscription_quota_cycles.added == []


@pytest.mark.asyncio
async def test_assessment_activation_rejects_non_authoritative_price_source() -> None:
    plan = _plan()
    unit = _UnitOfWork(plan)
    service = AssessmentSubscriptionActivationService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: datetime(2026, 8, 9, 20, 0, tzinfo=UTC),
    )

    with pytest.raises(AssessmentCommercialTermsError, match="price_source"):
        await service.activate(
            outcome=_outcome(),
            commercial_terms=_commercial_terms(
                price_source="catalog",
                source_reference="academic",
            ),
            entitlement_plan_id=plan.id,
            correlation_id="corr-assessment-invalid-price",
            idempotency_key="idem-assessment-invalid-price",
        )

    assert unit.commit_count == 0
    assert unit.subscriptions.by_id == {}
    assert unit.subscription_quota_cycles.added == []
