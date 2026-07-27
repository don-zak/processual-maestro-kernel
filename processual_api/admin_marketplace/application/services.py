from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from processual_api.admin_marketplace.application.audit import (
    build_audit_record,
)
from processual_api.admin_marketplace.application.commands import (
    CreateOfferCommand,
    CreateOrderCommand,
    CreatePlanCommand,
    DecideEntitlementActivationCommand,
    DecideOfferCommand,
    DecidePaymentVerificationCommand,
    RecordChannelEligibilityCommand,
    RecordChannelSelectionCommand,
)
from processual_api.admin_marketplace.application.errors import (
    AdminMarketplaceActivationPolicyError,
    AdminMarketplaceChannelPolicyError,
    AdminMarketplaceResourceNotFoundError,
    AdminMarketplaceTransitionError,
)
from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAction,
    require_admin_marketplace_authority,
)
from processual_api.admin_marketplace.contracts import (
    CommercialDecisionOutcome,
    CustomerChannelSelectionContract,
    OfferStatus,
    PaymentVerificationStatus,
    SalesChannelEligibilityContract,
)
from processual_api.admin_marketplace.models import (
    AdminMarketChannelEligibility,
    AdminMarketChannelSelection,
    AdminMarketCommercialDecision,
    AdminMarketEntitlementActivation,
    AdminMarketOffer,
    AdminMarketOrder,
    AdminMarketPaymentVerification,
    AdminMarketPlan,
)
from processual_api.admin_marketplace.persistence.protocols import (
    AdminMarketplaceUnitOfWork,
)

type UnitOfWorkFactory = Callable[
    [],
    AdminMarketplaceUnitOfWork,
]


OFFER_TRANSITIONS = {
    OfferStatus.DRAFT: {
        OfferStatus.UNDER_REVIEW,
        OfferStatus.RETIRED,
    },
    OfferStatus.UNDER_REVIEW: {
        OfferStatus.APPROVED,
        OfferStatus.DRAFT,
        OfferStatus.RETIRED,
    },
    OfferStatus.APPROVED: {
        OfferStatus.PUBLISHED,
        OfferStatus.SUSPENDED,
        OfferStatus.RETIRED,
    },
    OfferStatus.PUBLISHED: {
        OfferStatus.SUSPENDED,
        OfferStatus.RETIRED,
    },
    OfferStatus.SUSPENDED: {
        OfferStatus.PUBLISHED,
        OfferStatus.RETIRED,
    },
    OfferStatus.RETIRED: set(),
}


class AdminMarketplaceCommercialCoreService:
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create_plan(
        self,
        command: CreatePlanCommand,
    ) -> AdminMarketPlan:
        require_admin_marketplace_authority(
            context=command.context.authority,
            action=AdminMarketplaceAction.CREATE_OFFER,
        )

        plan = AdminMarketPlan(
            id=command.plan_id,
            plan_code=command.plan_code,
            display_name=command.display_name,
            entitlement_profile_ref=(command.entitlement_profile_ref),
            quota_profile_ref=command.quota_profile_ref,
            metadata_json=dict(command.metadata),
        )

        async with self._unit_of_work_factory() as unit:
            unit.plans.add(plan)
            unit.commercial_audit.append(
                build_audit_record(
                    authority=command.context.authority,
                    correlation_id=(command.context.correlation_id),
                    action="authority_checked",
                    resource_type="plan",
                    resource_id=str(plan.id),
                    outcome="allowed",
                    reason_code=("super_administrator_authorized"),
                    new_state={
                        "plan_code": plan.plan_code,
                        "display_name": plan.display_name,
                    },
                    occurred_at=self._clock(),
                )
            )
            await unit.commit()

        return plan

    async def create_offer(
        self,
        command: CreateOfferCommand,
    ) -> AdminMarketOffer:
        require_admin_marketplace_authority(
            context=command.context.authority,
            action=AdminMarketplaceAction.CREATE_OFFER,
        )

        offer = AdminMarketOffer(
            id=command.offer_id,
            offer_code=command.offer_code,
            plan_id=command.plan_id,
            display_name=command.display_name,
            currency=command.currency,
            amount=command.amount,
            status=command.status.value,
            effective_at=command.effective_at,
            expires_at=command.expires_at,
            customer_specific=command.customer_specific,
        )

        async with self._unit_of_work_factory() as unit:
            plan = await unit.plans.get_by_id(command.plan_id)
            if plan is None:
                raise AdminMarketplaceResourceNotFoundError("Marketplace plan does not exist.")

            unit.offers.add(offer)
            unit.commercial_audit.append(
                build_audit_record(
                    authority=command.context.authority,
                    correlation_id=(command.context.correlation_id),
                    action="authority_checked",
                    resource_type="offer",
                    resource_id=str(offer.id),
                    outcome="allowed",
                    reason_code=("super_administrator_authorized"),
                    new_state={
                        "offer_code": offer.offer_code,
                        "status": offer.status,
                        "plan_id": str(offer.plan_id),
                    },
                    occurred_at=self._clock(),
                )
            )
            await unit.commit()

        return offer

    async def decide_offer(
        self,
        command: DecideOfferCommand,
    ) -> AdminMarketOffer:
        action = (
            AdminMarketplaceAction.PUBLISH_OFFER
            if command.status is OfferStatus.PUBLISHED
            else AdminMarketplaceAction.REVISE_OFFER
        )

        require_admin_marketplace_authority(
            context=command.context.authority,
            action=action,
        )

        async with self._unit_of_work_factory() as unit:
            offer = await unit.offers.get_by_id(
                command.offer_id,
                for_update=True,
            )
            if offer is None:
                raise AdminMarketplaceResourceNotFoundError("Marketplace offer does not exist.")

            previous_status = OfferStatus(offer.status)
            allowed = OFFER_TRANSITIONS.get(
                previous_status,
                set(),
            )
            if command.status not in allowed:
                raise AdminMarketplaceTransitionError("Marketplace offer transition is not allowed.")

            offer.status = command.status.value

            decision = AdminMarketCommercialDecision(
                id=command.decision_id,
                decision_ref=command.decision_ref,
                action="offer_status_change",
                resource_type="offer",
                resource_id=str(offer.id),
                outcome=(CommercialDecisionOutcome.APPROVED.value),
                reason_code=command.reason_code,
            )

            unit.commercial_decisions.add(decision)
            unit.commercial_audit.append(
                build_audit_record(
                    authority=command.context.authority,
                    correlation_id=(command.context.correlation_id),
                    action="offer_decided",
                    resource_type="offer",
                    resource_id=str(offer.id),
                    outcome="allowed",
                    reason_code=command.reason_code,
                    previous_state={
                        "status": previous_status.value,
                    },
                    new_state={
                        "status": offer.status,
                    },
                    occurred_at=self._clock(),
                )
            )
            await unit.commit()

        return offer

    async def record_channel_eligibility(
        self,
        command: RecordChannelEligibilityCommand,
    ) -> AdminMarketChannelEligibility:
        require_admin_marketplace_authority(
            context=command.context.authority,
            action=(AdminMarketplaceAction.CHANGE_CHANNEL_ELIGIBILITY),
        )

        policy = SalesChannelEligibilityContract(
            country_code=command.country_code,
            maestro_direct_status=(command.maestro_direct_status),
            lemon_squeezy_status=(command.lemon_squeezy_status),
            customer_choice_allowed=(command.customer_choice_allowed),
            admin_review_required=(command.admin_review_required),
            restriction_reason=(command.restriction_reason),
            automatic_activation_allowed=(command.automatic_activation_allowed),
        )

        eligibility = AdminMarketChannelEligibility(
            id=command.eligibility_id,
            customer_ref=command.customer_ref,
            country_code=policy.country_code,
            maestro_direct_status=(policy.maestro_direct_status.value),
            lemon_squeezy_status=(policy.lemon_squeezy_status.value),
            customer_choice_allowed=(policy.customer_choice_allowed),
            admin_review_required=(policy.admin_review_required),
            restriction_reason=(policy.restriction_reason),
            automatic_activation_allowed=(policy.automatic_activation_allowed),
        )

        audit_outcome = "requires_review" if command.admin_review_required else "allowed"

        async with self._unit_of_work_factory() as unit:
            unit.channel_eligibilities.add(eligibility)
            unit.commercial_audit.append(
                build_audit_record(
                    authority=command.context.authority,
                    correlation_id=(command.context.correlation_id),
                    action=("channel_eligibility_decided"),
                    resource_type=("sales_channel_eligibility"),
                    resource_id=str(eligibility.id),
                    outcome=audit_outcome,
                    reason_code=(command.restriction_reason or "channel_policy_evaluated"),
                    new_state={
                        "customer_ref": (eligibility.customer_ref),
                        "maestro_direct_status": (eligibility.maestro_direct_status),
                        "lemon_squeezy_status": (eligibility.lemon_squeezy_status),
                    },
                    occurred_at=self._clock(),
                )
            )
            await unit.commit()

        return eligibility

    async def record_channel_selection(
        self,
        command: RecordChannelSelectionCommand,
    ) -> AdminMarketChannelSelection:
        require_admin_marketplace_authority(
            context=command.context.authority,
            action=AdminMarketplaceAction.DECIDE_ORDER,
        )

        contract = CustomerChannelSelectionContract(
            customer_id=command.customer_ref,
            selected_channel=command.selected_channel,
            eligible_channels=command.eligible_channels,
            customer_consented=(command.customer_consented),
            administrator_override_reason=(command.administrator_override_reason),
        )

        selection = AdminMarketChannelSelection(
            id=command.selection_id,
            customer_ref=contract.customer_id,
            selected_channel=(contract.selected_channel.value),
            eligible_channels_json=[
                channel.value
                for channel in sorted(
                    contract.eligible_channels,
                    key=lambda value: value.value,
                )
            ],
            customer_consented=(contract.customer_consented),
            administrator_override_reason=(contract.administrator_override_reason),
        )

        async with self._unit_of_work_factory() as unit:
            unit.channel_selections.add(selection)
            unit.commercial_audit.append(
                build_audit_record(
                    authority=command.context.authority,
                    correlation_id=(command.context.correlation_id),
                    action="channel_selected",
                    resource_type=("sales_channel_eligibility"),
                    resource_id=str(selection.id),
                    outcome="allowed",
                    reason_code=(
                        "customer_channel_choice_recorded"
                        if command.customer_consented
                        else "administrator_override_recorded"
                    ),
                    new_state={
                        "customer_ref": (selection.customer_ref),
                        "selected_channel": (selection.selected_channel),
                    },
                    occurred_at=self._clock(),
                )
            )
            await unit.commit()

        return selection

    async def create_order(
        self,
        command: CreateOrderCommand,
    ) -> AdminMarketOrder:
        require_admin_marketplace_authority(
            context=command.context.authority,
            action=AdminMarketplaceAction.DECIDE_ORDER,
        )

        async with self._unit_of_work_factory() as unit:
            offer = await unit.offers.get_by_id(command.offer_id)
            if offer is None:
                raise AdminMarketplaceResourceNotFoundError("Marketplace offer does not exist.")
            if offer.status != OfferStatus.PUBLISHED.value:
                raise AdminMarketplaceTransitionError("Only a published offer can be ordered.")

            eligibility = (
                await unit.channel_eligibilities.get_by_customer_ref(
                    command.customer_ref,
                    for_update=True,
                )
            )
            if eligibility is None:
                raise AdminMarketplaceChannelPolicyError(
                    "Sales-channel eligibility has not been decided."
                )
            if eligibility.admin_review_required:
                raise AdminMarketplaceChannelPolicyError(
                    "Sales-channel eligibility requires "
                    "administrator review."
                )

            channel_status = {
                "maestro_direct": (
                    eligibility.maestro_direct_status
                ),
                "lemon_squeezy": (
                    eligibility.lemon_squeezy_status
                ),
            }[command.selected_channel.value]

            if channel_status != "eligible":
                raise AdminMarketplaceChannelPolicyError(
                    "The selected sales channel is not eligible."
                )

            order = AdminMarketOrder(
                id=command.order_id,
                order_ref=command.order_ref,
                customer_ref=command.customer_ref,
                offer_id=command.offer_id,
                selected_channel=(command.selected_channel.value),
                status="submitted",
            )

            unit.orders.add(order)
            unit.commercial_audit.append(
                build_audit_record(
                    authority=command.context.authority,
                    correlation_id=(command.context.correlation_id),
                    action="authority_checked",
                    resource_type="order",
                    resource_id=str(order.id),
                    outcome="allowed",
                    reason_code="order_created",
                    new_state={
                        "status": order.status,
                        "selected_channel": (order.selected_channel),
                    },
                    occurred_at=self._clock(),
                )
            )
            await unit.commit()

        return order

    async def decide_payment_verification(
        self,
        command: DecidePaymentVerificationCommand,
    ) -> AdminMarketPaymentVerification:
        require_admin_marketplace_authority(
            context=command.context.authority,
            action=AdminMarketplaceAction.VERIFY_PAYMENT,
        )

        async with self._unit_of_work_factory() as unit:
            order = await unit.orders.get_by_id(
                command.order_id,
                for_update=True,
            )
            if order is None:
                raise AdminMarketplaceResourceNotFoundError("Marketplace order does not exist.")

            verification = AdminMarketPaymentVerification(
                id=command.verification_id,
                verification_ref=(command.verification_ref),
                order_id=command.order_id,
                status=command.status.value,
                safe_reference=command.safe_reference,
            )

            if command.status is PaymentVerificationStatus.VERIFIED:
                order.status = "approved"
            elif command.status is PaymentVerificationStatus.REJECTED:
                order.status = "rejected"
            else:
                order.status = "awaiting_payment_verification"

            decision_outcome = {
                PaymentVerificationStatus.VERIFIED: (CommercialDecisionOutcome.APPROVED),
                PaymentVerificationStatus.REJECTED: (CommercialDecisionOutcome.DENIED),
                PaymentVerificationStatus.REQUIRES_REVIEW: (CommercialDecisionOutcome.REQUIRES_REVIEW),
                PaymentVerificationStatus.PENDING: (CommercialDecisionOutcome.REQUIRES_REVIEW),
            }[command.status]

            decision = AdminMarketCommercialDecision(
                id=command.decision_id,
                decision_ref=command.decision_ref,
                action="payment_verification",
                resource_type="payment_verification",
                resource_id=str(verification.id),
                outcome=decision_outcome.value,
                reason_code=command.reason_code,
            )

            unit.payment_verifications.add(verification)
            unit.commercial_decisions.add(decision)

            unit.commercial_audit.append(
                build_audit_record(
                    authority=command.context.authority,
                    correlation_id=(command.context.correlation_id),
                    action=("payment_verification_decided"),
                    resource_type=("payment_verification"),
                    resource_id=str(verification.id),
                    outcome={
                        CommercialDecisionOutcome.APPROVED: ("allowed"),
                        CommercialDecisionOutcome.DENIED: ("denied"),
                        CommercialDecisionOutcome.REQUIRES_REVIEW: ("requires_review"),
                    }[decision_outcome],
                    reason_code=command.reason_code,
                    new_state={
                        "status": verification.status,
                        "order_id": str(verification.order_id),
                    },
                    metadata={
                        "automatic_activation": "false",
                    },
                    occurred_at=self._clock(),
                )
            )

            # Payment verification deliberately does not create
            # an entitlement activation or active subscription.
            await unit.commit()

        return verification

    async def decide_entitlement_activation(
        self,
        command: DecideEntitlementActivationCommand,
    ) -> AdminMarketEntitlementActivation | None:
        require_admin_marketplace_authority(
            context=command.context.authority,
            action=(AdminMarketplaceAction.ACTIVATE_SUBSCRIPTION),
        )

        if command.automatic_activation_allowed:
            raise AdminMarketplaceActivationPolicyError("Automatic entitlement activation is forbidden.")

        async with self._unit_of_work_factory() as unit:
            subscription = await unit.subscriptions.get_by_id(
                command.subscription_id,
                for_update=True,
            )
            if subscription is None:
                raise AdminMarketplaceResourceNotFoundError("Marketplace subscription does not exist.")

            decision = AdminMarketCommercialDecision(
                id=command.decision_id,
                decision_ref=command.decision_ref,
                action="subscription_activation",
                resource_type="subscription",
                resource_id=str(subscription.id),
                outcome=command.outcome.value,
                reason_code=command.reason_code,
            )
            unit.commercial_decisions.add(decision)

            activation = None
            if command.outcome is CommercialDecisionOutcome.APPROVED:
                activation = AdminMarketEntitlementActivation(
                    id=command.activation_id,
                    activation_ref=(command.activation_ref),
                    customer_ref=(command.customer_ref),
                    subscription_id=(command.subscription_id),
                    entitlement_profile_ref=(command.entitlement_profile_ref),
                    automatic_activation_allowed=False,
                )
                unit.entitlement_activations.add(activation)
                subscription.status = "active"

            audit_outcome = {
                CommercialDecisionOutcome.APPROVED: ("allowed"),
                CommercialDecisionOutcome.DENIED: ("denied"),
                CommercialDecisionOutcome.REQUIRES_REVIEW: ("requires_review"),
            }[command.outcome]

            unit.commercial_audit.append(
                build_audit_record(
                    authority=command.context.authority,
                    correlation_id=(command.context.correlation_id),
                    action=("subscription_activation_decided"),
                    resource_type="subscription",
                    resource_id=str(subscription.id),
                    outcome=audit_outcome,
                    reason_code=command.reason_code,
                    new_state={
                        "status": subscription.status,
                        "activated": str(activation is not None).lower(),
                    },
                    metadata={
                        "automatic_activation": "false",
                    },
                    occurred_at=self._clock(),
                )
            )
            await unit.commit()

        return activation


__all__ = [
    "AdminMarketplaceCommercialCoreService",
    "OFFER_TRANSITIONS",
    "UnitOfWorkFactory",
]
