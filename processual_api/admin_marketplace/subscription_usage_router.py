from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)
from processual_api.admin_marketplace.router import router
from processual_api.admin_marketplace.subscription_runtime import (
    SubscriptionRuntimeError,
)
from processual_api.admin_marketplace.subscription_usage_service import (
    record_subscription_usage_factory,
)
from processual_api.auth.session_router import get_identity_user
from processual_api.db.session import get_session_factory


class SubscriptionUsageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subscription_id: uuid.UUID
    metric_code: str = Field(min_length=1, max_length=128)
    units: int = Field(gt=0, le=2_147_483_647)
    dimensions: dict[str, object] = Field(default_factory=dict)


class SubscriptionUsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    usage_id: uuid.UUID
    subscription_id: uuid.UUID
    metric_code: str
    units: int


def _uow_factory() -> SqlAlchemyAdminMarketplaceUnitOfWork:
    return SqlAlchemyAdminMarketplaceUnitOfWork(get_session_factory())


@router.post(
    "/subscriptions/usage",
    response_model=SubscriptionUsageResponse,
    status_code=201,
)
async def record_subscription_usage_endpoint(
    body: SubscriptionUsageRequest,
    current_user: dict = Depends(get_identity_user),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=512),
) -> SubscriptionUsageResponse:
    try:
        customer_ref = str(uuid.UUID(str(current_user["user_id"])))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Usage recording denied.") from exc

    record_usage = record_subscription_usage_factory(uow_factory=_uow_factory)
    try:
        usage = await record_usage(
            subscription_id=body.subscription_id,
            customer_ref=customer_ref,
            metric_code=body.metric_code,
            units=body.units,
            idempotency_key=idempotency_key,
            dimensions=body.dimensions,
        )
    except SubscriptionRuntimeError as exc:
        message = str(exc)
        status_code = 409 if "quota limit exceeded" in message else 403
        raise HTTPException(
            status_code=status_code,
            detail="Usage recording denied.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Usage service is temporarily unavailable.",
        ) from exc

    return SubscriptionUsageResponse(
        usage_id=usage.id,
        subscription_id=usage.subscription_id,
        metric_code=usage.metric_code,
        units=usage.units,
    )
