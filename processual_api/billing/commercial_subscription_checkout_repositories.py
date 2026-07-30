from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.billing.commercial_subscription_checkout_models import (
    CommercialSubscriptionActivationDecisionRow,
    CommercialSubscriptionCheckoutOrderRow,
    CommercialSubscriptionPaymentEvidenceRow,
)
from processual_api.billing.commercial_subscription_checkout_service import (
    CommercialActivationDecision,
    CommercialCheckoutChannel,
    CommercialCheckoutOrderState,
    CommercialDecisionOutcome,
    CommercialPaymentEvidence,
    PaymentEvidenceOutcome,
    SubscriptionCheckoutOrder,
)


def _order_from_row(row: CommercialSubscriptionCheckoutOrderRow) -> SubscriptionCheckoutOrder:
    return SubscriptionCheckoutOrder(
        order_id=row.order_id,
        tenant_id=row.tenant_id,
        subscription_id=row.subscription_id,
        customer_reference=row.customer_reference,
        plan_code=row.plan_code,
        included_units=row.included_units,
        billing_cycle_reference=row.billing_cycle_reference,
        cycle_started_at=row.cycle_started_at,
        cycle_ends_at=row.cycle_ends_at,
        authoritative_price_usd=row.authoritative_price_usd,
        selected_channel=CommercialCheckoutChannel(row.selected_channel),
        settlement_currency=row.settlement_currency,
        settlement_amount=row.settlement_amount,
        quote_reference=row.quote_reference,
        quote_expires_at=row.quote_expires_at,
        billing_country=row.billing_country,
        tunisian_address_eligible=row.tunisian_address_eligible,
        customer_choice_preserved=row.customer_choice_preserved,
        state=CommercialCheckoutOrderState(row.state),
        idempotency_key=row.idempotency_key,
        created_at=row.created_at,
        version=row.version,
    )


def _payment_from_row(row: CommercialSubscriptionPaymentEvidenceRow) -> CommercialPaymentEvidence:
    return CommercialPaymentEvidence(
        evidence_id=row.evidence_id,
        order_id=row.order_id,
        provider_reference=row.provider_reference,
        channel=CommercialCheckoutChannel(row.channel),
        outcome=PaymentEvidenceOutcome(row.outcome),
        verified_amount=row.verified_amount,
        verified_currency=row.verified_currency,
        immutable_evidence_reference=row.immutable_evidence_reference,
        observed_at=row.observed_at,
        idempotency_key=row.idempotency_key,
    )


def _decision_from_row(
    row: CommercialSubscriptionActivationDecisionRow,
) -> CommercialActivationDecision:
    return CommercialActivationDecision(
        decision_id=row.decision_id,
        order_id=row.order_id,
        outcome=CommercialDecisionOutcome(row.outcome),
        actor_reference=row.actor_reference,
        authority_reference=row.authority_reference,
        approval_reference=row.approval_reference,
        reason=row.reason,
        occurred_at=row.occurred_at,
        idempotency_key=row.idempotency_key,
    )


class SqlAlchemySubscriptionCheckoutOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, order_id, *, for_update=False):
        statement = select(CommercialSubscriptionCheckoutOrderRow).where(
            CommercialSubscriptionCheckoutOrderRow.order_id == order_id
        )
        if for_update:
            statement = statement.with_for_update()
        row = await self._session.scalar(statement)
        return None if row is None else _order_from_row(row)

    async def get_by_idempotency_key(self, idempotency_key):
        row = await self._session.scalar(
            select(CommercialSubscriptionCheckoutOrderRow).where(
                CommercialSubscriptionCheckoutOrderRow.idempotency_key == idempotency_key
            )
        )
        return None if row is None else _order_from_row(row)

    def add(self, order):
        self._session.add(
            CommercialSubscriptionCheckoutOrderRow(
                order_id=order.order_id,
                tenant_id=order.tenant_id,
                subscription_id=order.subscription_id,
                customer_reference=order.customer_reference,
                plan_code=order.plan_code,
                included_units=order.included_units,
                billing_cycle_reference=order.billing_cycle_reference,
                cycle_started_at=order.cycle_started_at,
                cycle_ends_at=order.cycle_ends_at,
                authoritative_price_usd=order.authoritative_price_usd,
                selected_channel=order.selected_channel.value,
                settlement_currency=order.settlement_currency,
                settlement_amount=order.settlement_amount,
                quote_reference=order.quote_reference,
                quote_expires_at=order.quote_expires_at,
                billing_country=order.billing_country,
                tunisian_address_eligible=order.tunisian_address_eligible,
                customer_choice_preserved=order.customer_choice_preserved,
                state=order.state.value,
                idempotency_key=order.idempotency_key,
                created_at=order.created_at,
                version=order.version,
            )
        )

    def replace(self, order):
        row = self._session.get(CommercialSubscriptionCheckoutOrderRow, order.order_id)

        async def apply():
            target = await row
            if target is None:
                raise RuntimeError("checkout order row is missing")
            target.state = order.state.value
            target.version = order.version

        self._session.info.setdefault("checkout_pending_updates", []).append(apply)


class SqlAlchemyCommercialPaymentEvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_provider_reference(self, provider_reference):
        row = await self._session.scalar(
            select(CommercialSubscriptionPaymentEvidenceRow).where(
                CommercialSubscriptionPaymentEvidenceRow.provider_reference == provider_reference
            )
        )
        return None if row is None else _payment_from_row(row)

    async def get_latest_for_order(self, order_id):
        row = await self._session.scalar(
            select(CommercialSubscriptionPaymentEvidenceRow)
            .where(CommercialSubscriptionPaymentEvidenceRow.order_id == order_id)
            .order_by(CommercialSubscriptionPaymentEvidenceRow.observed_at.desc())
            .limit(1)
        )
        return None if row is None else _payment_from_row(row)

    def add(self, evidence):
        self._session.add(
            CommercialSubscriptionPaymentEvidenceRow(
                evidence_id=evidence.evidence_id,
                order_id=evidence.order_id,
                provider_reference=evidence.provider_reference,
                channel=evidence.channel.value,
                outcome=evidence.outcome.value,
                verified_amount=evidence.verified_amount,
                verified_currency=evidence.verified_currency,
                immutable_evidence_reference=evidence.immutable_evidence_reference,
                observed_at=evidence.observed_at,
                idempotency_key=evidence.idempotency_key,
            )
        )


class SqlAlchemyCommercialActivationDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_idempotency_key(self, idempotency_key):
        row = await self._session.scalar(
            select(CommercialSubscriptionActivationDecisionRow).where(
                CommercialSubscriptionActivationDecisionRow.idempotency_key == idempotency_key
            )
        )
        return None if row is None else _decision_from_row(row)

    async def get_latest_for_order(self, order_id):
        row = await self._session.scalar(
            select(CommercialSubscriptionActivationDecisionRow)
            .where(CommercialSubscriptionActivationDecisionRow.order_id == order_id)
            .order_by(CommercialSubscriptionActivationDecisionRow.occurred_at.desc())
            .limit(1)
        )
        return None if row is None else _decision_from_row(row)

    def add(self, decision):
        self._session.add(
            CommercialSubscriptionActivationDecisionRow(
                decision_id=decision.decision_id,
                order_id=decision.order_id,
                outcome=decision.outcome.value,
                actor_reference=decision.actor_reference,
                authority_reference=decision.authority_reference,
                approval_reference=decision.approval_reference,
                reason=decision.reason,
                occurred_at=decision.occurred_at,
                idempotency_key=decision.idempotency_key,
            )
        )


async def apply_checkout_pending_updates(session: AsyncSession) -> None:
    callbacks = session.info.pop("checkout_pending_updates", [])
    for callback in callbacks:
        await callback()
