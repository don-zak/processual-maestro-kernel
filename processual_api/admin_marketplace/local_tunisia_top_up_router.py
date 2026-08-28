from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAction,
    require_admin_marketplace_authority,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
    AdminMarketplaceStepUpRequiredError,
)
from processual_api.admin_marketplace.local_tunisia_top_up_payment import (
    LocalTunisiaTopUpPaymentError,
    VerifyLocalTunisiaTopUpPaymentCommand,
    verify_local_tunisia_top_up_payment_factory,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)
from processual_api.admin_marketplace.router import (
    _identity_principal,
    get_admin_marketplace_runtime,
    router,
)
from processual_api.admin_marketplace.runtime import AdminMarketplaceRuntime
from processual_api.admin_marketplace.subscription_top_up_order import (
    CreateSubscriptionTopUpOrderCommand,
    SubscriptionTopUpOrderError,
    create_subscription_top_up_order_factory,
)
from processual_api.admin_marketplace.subscription_top_up_purchase_router import (
    _resolve_current_cycle_id,
)
from processual_api.admin_marketplace.subscription_top_up_reversal import (
    ReverseSubscriptionTopUpCommand,
    SubscriptionTopUpReversalError,
    reverse_subscription_top_up_factory,
)
from processual_api.auth.session_router import get_identity_user
from processual_api.billing.commercial_currency_settlement_contracts import (
    ExchangeRateQuote,
)
from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)
from processual_api.db.session import get_session_factory

_LOCAL_PURCHASE_FLAG = "MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED"
_LOCAL_ADMIN_FLAG = "MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED"
_RATE_ENV = "MAESTRO_TUNISIA_USD_TND_RATE"
_RATE_SOURCE_ENV = "MAESTRO_TUNISIA_FX_SOURCE"
_RATE_REFERENCE_ENV = "MAESTRO_TUNISIA_FX_REFERENCE"
_RATE_TTL_ENV = "MAESTRO_TUNISIA_FX_TTL_SECONDS"
_RATE_OBSERVED_AT_ENV = "MAESTRO_TUNISIA_FX_OBSERVED_AT"


class LocalTunisiaTopUpPurchaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subscription_id: uuid.UUID
    requested_units: int = Field(gt=0, le=2_147_483_647)


class LocalTunisiaTopUpPurchaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order_id: uuid.UUID
    subscription_id: uuid.UUID
    quota_cycle_id: uuid.UUID
    requested_units: int
    settlement_currency: str
    settlement_amount: str
    payment_reference: str
    replayed: bool


class LocalTunisiaTopUpVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    customer_ref: str = Field(min_length=1, max_length=128)
    provider_reference: str = Field(min_length=1, max_length=255)
    amount_tnd: Decimal = Field(gt=0)
    evidence_reference: str = Field(min_length=1, max_length=500)


class LocalTunisiaTopUpVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order_id: uuid.UUID
    grant_id: uuid.UUID
    units: int
    replayed: bool


class TopUpReversalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    provider_event_ref: str = Field(min_length=1, max_length=255)
    reason_code: str = Field(pattern="^(provider_refund|chargeback|fraud)$")


class TopUpReversalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reversal_id: uuid.UUID
    order_id: uuid.UUID
    grant_id: uuid.UUID
    units: int
    outcome: str
    replayed: bool


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _uow_factory() -> SqlAlchemyAdminMarketplaceUnitOfWork:
    return SqlAlchemyAdminMarketplaceUnitOfWork(get_session_factory())


class EnvironmentTunisiaExchangeRateProvider:
    async def quote_usd_to_tnd(self, *, requested_at: datetime) -> ExchangeRateQuote:
        rate_raw = os.environ.get(_RATE_ENV, "").strip()
        source = os.environ.get(_RATE_SOURCE_ENV, "").strip()
        reference = os.environ.get(_RATE_REFERENCE_ENV, "").strip()
        ttl_raw = os.environ.get(_RATE_TTL_ENV, "").strip()
        observed_raw = os.environ.get(_RATE_OBSERVED_AT_ENV, "").strip()
        try:
            rate = Decimal(rate_raw)
            ttl_seconds = int(ttl_raw)
            observed_at = datetime.fromisoformat(observed_raw.replace("Z", "+00:00"))
        except (InvalidOperation, ValueError) as exc:
            raise SubscriptionTopUpOrderError(
                "Tunisia-local exchange-rate configuration is invalid."
            ) from exc
        if (
            not rate.is_finite()
            or rate <= 0
            or ttl_seconds <= 0
            or ttl_seconds > 86_400
            or observed_at.tzinfo is None
        ):
            raise SubscriptionTopUpOrderError(
                "Tunisia-local exchange-rate configuration is invalid."
            )
        if requested_at.tzinfo is None:
            raise SubscriptionTopUpOrderError(
                "Tunisia-local exchange-rate request time is invalid."
            )
        if not source or not reference:
            raise SubscriptionTopUpOrderError(
                "Tunisia-local exchange-rate configuration is incomplete."
            )
        observed_at = observed_at.astimezone(UTC)
        requested_at = requested_at.astimezone(UTC)
        expires_at = observed_at + timedelta(seconds=ttl_seconds)
        if observed_at > requested_at:
            raise SubscriptionTopUpOrderError(
                "Tunisia-local exchange-rate observation is in the future."
            )
        if requested_at >= expires_at:
            raise SubscriptionTopUpOrderError(
                "Tunisia-local exchange-rate quote is expired."
            )
        return ExchangeRateQuote(
            base_currency="USD",
            settlement_currency="TND",
            rate=rate,
            source=source,
            reference=reference,
            observed_at=observed_at,
            expires_at=expires_at,
        )


async def _local_eligibility(
    customer_ref: str,
    subscription_id: uuid.UUID,
    requested_at: datetime,
) -> bool:
    del subscription_id, requested_at
    async with _uow_factory() as uow:
        eligibility = await uow.channel_eligibilities.get_by_customer_ref(customer_ref)
        if eligibility is None:
            return False
        country = str(getattr(eligibility, "country_code", "") or "").strip().upper()
        address_status = str(getattr(eligibility, "address_status", "") or "").strip().lower()
        channel_status = str(getattr(eligibility, "maestro_direct_status", "") or "").strip().lower()
        review_required = bool(getattr(eligibility, "admin_review_required", False))
        return (
            country == "TN"
            and address_status == "confirmed"
            and channel_status == "eligible"
            and not review_required
        )


async def _require_admin_action(
    *,
    current_user: dict,
    runtime: AdminMarketplaceRuntime,
    action: AdminMarketplaceAction,
) -> None:
    user_id, session_id = _identity_principal(current_user)
    authority = await runtime.authority_resolver.resolve(
        user_id=user_id,
        session_id=session_id,
    )
    require_admin_marketplace_authority(context=authority, action=action)


@router.post(
    "/subscriptions/top-ups/local-tunisia/purchase",
    response_model=LocalTunisiaTopUpPurchaseResponse,
    status_code=201,
)
async def purchase_local_tunisia_top_up(
    body: LocalTunisiaTopUpPurchaseRequest,
    current_user: dict = Depends(get_identity_user),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=512),
) -> LocalTunisiaTopUpPurchaseResponse:
    if not _enabled(_LOCAL_PURCHASE_FLAG):
        raise HTTPException(status_code=503, detail="Tunisia-local top-up purchasing is unavailable.")
    try:
        customer_ref = str(uuid.UUID(str(current_user["user_id"])))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Tunisia-local top-up purchasing denied.") from exc

    created_at = datetime.now(UTC)
    try:
        quota_cycle_id = await _resolve_current_cycle_id(
            subscription_id=body.subscription_id,
            customer_ref=customer_ref,
            at=created_at,
        )
        order_id = uuid.uuid5(
            uuid.UUID("831a7913-4093-56ac-bb49-58c1fd998d17"),
            f"{customer_ref}:{idempotency_key.strip()}",
        )
        create_order = create_subscription_top_up_order_factory(
            unit_of_work_factory=_uow_factory,
            local_tunisia_eligibility_resolver=_local_eligibility,
            exchange_rate_provider=EnvironmentTunisiaExchangeRateProvider(),
        )
        result = await create_order(
            CreateSubscriptionTopUpOrderCommand(
                order_id=order_id,
                customer_ref=customer_ref,
                subscription_id=body.subscription_id,
                quota_cycle_id=quota_cycle_id,
                requested_units=body.requested_units,
                channel=TopUpCheckoutChannel.LOCAL_TUNISIA,
                idempotency_key=f"local-top-up:{customer_ref}:{idempotency_key.strip()}",
                created_at=created_at,
            )
        )
    except SubscriptionTopUpOrderError as exc:
        raise HTTPException(status_code=409, detail="Tunisia-local top-up order could not be created.") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Tunisia-local top-up purchasing is unavailable.") from exc

    return LocalTunisiaTopUpPurchaseResponse(
        order_id=result.order_id,
        subscription_id=body.subscription_id,
        quota_cycle_id=result.quota_cycle_id,
        requested_units=result.requested_units,
        settlement_currency=result.settlement_currency,
        settlement_amount=result.settlement_amount,
        payment_reference=f"topup-{result.order_id}",
        replayed=result.idempotent_replay,
    )


@router.post(
    "/top-ups/local-tunisia/{order_id}/verify",
    response_model=LocalTunisiaTopUpVerifyResponse,
)
async def verify_local_tunisia_top_up(
    order_id: uuid.UUID,
    body: LocalTunisiaTopUpVerifyRequest,
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(get_admin_marketplace_runtime),
) -> LocalTunisiaTopUpVerifyResponse:
    if not _enabled(_LOCAL_ADMIN_FLAG):
        raise HTTPException(status_code=503, detail="Tunisia-local top-up administration is unavailable.")
    try:
        await _require_admin_action(
            current_user=current_user,
            runtime=runtime,
            action=AdminMarketplaceAction.VERIFY_PAYMENT,
        )
        verify = verify_local_tunisia_top_up_payment_factory(unit_of_work_factory=_uow_factory)
        result = await verify(
            VerifyLocalTunisiaTopUpPaymentCommand(
                order_id=order_id,
                customer_ref=body.customer_ref,
                provider_reference=body.provider_reference,
                amount_tnd=body.amount_tnd,
                evidence_reference=body.evidence_reference,
                verified_at=datetime.now(UTC),
            )
        )
    except AdminMarketplaceStepUpRequiredError as exc:
        raise HTTPException(status_code=403, detail="Recent MFA step-up is required.") from exc
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(status_code=403, detail="Top-up payment verification denied.") from exc
    except LocalTunisiaTopUpPaymentError as exc:
        raise HTTPException(status_code=409, detail="Top-up payment verification failed.") from exc

    return LocalTunisiaTopUpVerifyResponse(
        order_id=result.order_id,
        grant_id=result.grant_id,
        units=result.units,
        replayed=result.replayed_grant,
    )


@router.post(
    "/top-ups/{order_id}/reversal",
    response_model=TopUpReversalResponse,
)
async def reconcile_top_up_reversal(
    order_id: uuid.UUID,
    body: TopUpReversalRequest,
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(get_admin_marketplace_runtime),
) -> TopUpReversalResponse:
    if not _enabled(_LOCAL_ADMIN_FLAG):
        raise HTTPException(status_code=503, detail="Top-up reconciliation is unavailable.")
    try:
        await _require_admin_action(
            current_user=current_user,
            runtime=runtime,
            action=AdminMarketplaceAction.RECONCILE_PAYMENT,
        )
        reverse = reverse_subscription_top_up_factory(unit_of_work_factory=_uow_factory)
        result = await reverse(
            ReverseSubscriptionTopUpCommand(
                order_id=order_id,
                provider_event_ref=body.provider_event_ref,
                reason_code=body.reason_code,
                reversed_at=datetime.now(UTC),
            )
        )
    except AdminMarketplaceStepUpRequiredError as exc:
        raise HTTPException(status_code=403, detail="Recent MFA step-up is required.") from exc
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(status_code=403, detail="Top-up reconciliation denied.") from exc
    except SubscriptionTopUpReversalError as exc:
        raise HTTPException(status_code=409, detail="Top-up reconciliation failed.") from exc

    return TopUpReversalResponse(
        reversal_id=result.reversal_id,
        order_id=result.order_id,
        grant_id=result.grant_id,
        units=result.units,
        outcome=result.outcome,
        replayed=result.idempotent_replay,
    )


__all__ = [
    "EnvironmentTunisiaExchangeRateProvider",
    "LocalTunisiaTopUpPurchaseRequest",
    "LocalTunisiaTopUpPurchaseResponse",
    "LocalTunisiaTopUpVerifyRequest",
    "LocalTunisiaTopUpVerifyResponse",
    "TopUpReversalRequest",
    "TopUpReversalResponse",
]
