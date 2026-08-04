from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict

from processual_api.admin_marketplace.direct_order_runtime import (
    DirectOrderRuntimeUnavailableError,
    build_direct_order_service,
)
from processual_api.admin_marketplace.direct_order_service import (
    DirectCommercialOrderResult,
    TunisiaDirectOrderService,
    TunisiaPaymentOptionResult,
)
from processual_api.admin_marketplace.errors import (
    DirectCommerceConflictError,
    DirectCommerceUnavailableError,
)
from processual_api.admin_marketplace.persistence.errors import (
    AdminMarketplacePersistenceError,
)
from processual_api.auth.session_router import get_identity_user
from processual_api.billing.subscription_preparation import (
    build_subscription_preparation,
)
from processual_api.billing.subscription_preparation_repository import (
    SqlAlchemySubscriptionPreparationRepository,
)
from processual_api.db.session import get_session_factory

router = APIRouter(prefix="/billing/subscription-preparation")


class TunisiaPaymentOptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible: bool
    reason_code: str
    address_status: str | None
    country_code: str | None
    sales_channel: str | None
    currency: str | None
    offer_ref: str | None
    offer_display_name: str | None
    billing_period: str | None
    amount: Decimal | None


class PaymentDestinationSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination_ref: str
    display_name: str
    destination_type: str
    institution_name: str
    account_holder_name: str
    masked_identifier: str
    instructions: str | None
    country_code: str
    currency: str
    sales_channel: str
    snapshot_at: str


class DirectCommercialOrderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: uuid.UUID
    order_ref: str
    offer_ref: str
    plan_ref: str
    billing_period: str
    sales_channel: str
    country_code: str
    currency: str
    subtotal_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: str
    contract_status: str
    payment_requirement: str
    payment_status: str
    payment_reference: str | None
    payment_destination: PaymentDestinationSnapshotResponse
    reason_code: str


async def get_direct_order_service() -> TunisiaDirectOrderService:
    try:
        return build_direct_order_service()
    except DirectOrderRuntimeUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Tunisian direct payment is temporarily unavailable.",
        ) from exc


def _identity(current_user: dict) -> tuple[uuid.UUID, str, str]:
    try:
        user_id = uuid.UUID(str(current_user["user_id"]))
        session_id = str(current_user["session_id"]).strip()
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid identity session.",
        ) from exc
    organization_id = str(current_user.get("organization_id") or "").strip()
    customer_ref = organization_id or str(user_id)
    if not session_id:
        raise HTTPException(status_code=401, detail="Invalid identity session.")
    return user_id, session_id, customer_ref


async def _verified_preparation(user_id: uuid.UUID) -> dict[str, object]:
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            preparation = await build_subscription_preparation(
                repository=SqlAlchemySubscriptionPreparationRepository(session),
                user_id=user_id,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Subscription preparation is unavailable.",
        ) from exc
    return preparation


def _unverified_option(preparation: dict[str, object]) -> TunisiaPaymentOptionResponse:
    return TunisiaPaymentOptionResponse(
        visible=False,
        reason_code=(
            "verified_registration_intent_required"
            if preparation.get("status") != "verified"
            else "valid_plan_preparation_required"
        ),
        address_status=None,
        country_code=None,
        sales_channel=None,
        currency=None,
        offer_ref=None,
        offer_display_name=None,
        billing_period=None,
        amount=None,
    )


def _option_response(
    result: TunisiaPaymentOptionResult,
) -> TunisiaPaymentOptionResponse:
    return TunisiaPaymentOptionResponse(
        visible=result.visible,
        reason_code=result.reason_code,
        address_status=result.address_status,
        country_code=result.country_code,
        sales_channel=result.sales_channel,
        currency=result.currency,
        offer_ref=result.offer_ref,
        offer_display_name=result.offer_display_name,
        billing_period=result.billing_period,
        amount=result.amount,
    )


def _order_response(
    result: DirectCommercialOrderResult,
) -> DirectCommercialOrderResponse:
    return DirectCommercialOrderResponse(
        order_id=result.order_id,
        order_ref=result.order_ref,
        offer_ref=result.offer_ref,
        plan_ref=result.plan_ref,
        billing_period=result.billing_period,
        sales_channel=result.sales_channel,
        country_code=result.country_code,
        currency=result.currency,
        subtotal_amount=result.subtotal_amount,
        tax_amount=result.tax_amount,
        total_amount=result.total_amount,
        status=result.status,
        contract_status=result.contract_status,
        payment_requirement=result.payment_requirement,
        payment_status=result.payment_status,
        payment_reference=result.payment_reference,
        payment_destination=PaymentDestinationSnapshotResponse.model_validate(
            result.payment_destination_snapshot
        ),
        reason_code=result.reason_code,
    )


@router.get(
    "/payment-options",
    response_model=TunisiaPaymentOptionResponse,
)
async def get_tunisia_payment_options(
    current_user: dict = Depends(get_identity_user),
    service: TunisiaDirectOrderService = Depends(get_direct_order_service),
) -> TunisiaPaymentOptionResponse:
    user_id, _, customer_ref = _identity(current_user)
    preparation = await _verified_preparation(user_id)
    plan_ref = preparation.get("plan_id")
    billing_period = preparation.get("billing_period")
    if not isinstance(plan_ref, str) or not isinstance(billing_period, str):
        return _unverified_option(preparation)
    try:
        result = await service.evaluate_payment_option(
            customer_ref=customer_ref,
            plan_ref=plan_ref,
            billing_period=billing_period,
        )
    except (ValueError, AdminMarketplacePersistenceError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Tunisian direct payment is temporarily unavailable.",
        ) from exc
    return _option_response(result)


@router.post(
    "/maestro-direct/orders",
    response_model=DirectCommercialOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tunisia_direct_order(
    current_user: dict = Depends(get_identity_user),
    service: TunisiaDirectOrderService = Depends(get_direct_order_service),
    correlation_id: str = Header(
        ...,
        alias="X-Correlation-ID",
        min_length=1,
        max_length=128,
    ),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=16,
        max_length=128,
    ),
) -> DirectCommercialOrderResponse:
    user_id, session_id, customer_ref = _identity(current_user)
    preparation = await _verified_preparation(user_id)
    plan_ref = preparation.get("plan_id")
    billing_period = preparation.get("billing_period")
    if not isinstance(plan_ref, str) or not isinstance(billing_period, str):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Tunisian direct payment is unavailable.",
                "reason_code": "verified_registration_intent_required",
            },
        )
    try:
        result = await service.create_order(
            actor_user_id=str(user_id),
            actor_session_id=session_id,
            customer_ref=customer_ref,
            plan_ref=plan_ref,
            billing_period=billing_period,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
    except DirectCommerceUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Tunisian direct payment is unavailable.",
                "reason_code": exc.reason_code,
            },
        ) from exc
    except DirectCommerceConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="The idempotency key conflicts with another order request.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid Tunisian direct order request.",
        ) from exc
    except AdminMarketplacePersistenceError as exc:
        raise HTTPException(
            status_code=503,
            detail="Tunisian direct payment is temporarily unavailable.",
        ) from exc
    return _order_response(result)


__all__ = [
    "DirectCommercialOrderResponse",
    "PaymentDestinationSnapshotResponse",
    "TunisiaPaymentOptionResponse",
    "create_tunisia_direct_order",
    "get_direct_order_service",
    "get_tunisia_payment_options",
    "router",
]
