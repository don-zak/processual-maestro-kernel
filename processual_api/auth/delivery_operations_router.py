from __future__ import annotations

import logging
import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import JSONResponse

from processual_api.auth.delivery_operations_http_contracts import (
    DeliveryOperationalMetricsResponseContract,
    DeliveryRedriveAcceptedResponseContract,
)
from processual_api.auth.delivery_operations_runtime import (
    DeliveryOperationsRuntime,
    DeliveryOperationsRuntimeUnavailableError,
    build_delivery_operations_runtime,
)
from processual_api.auth.delivery_operations_service import (
    DeliveryRedriveUnavailableError,
)
from processual_api.auth.security import (
    require_platform_admin_step_up,
)

logger = logging.getLogger(__name__)

GENERIC_UNAVAILABLE = (
    "Delivery operations temporarily unavailable."
)

platform_admin_step_up_dependency = (
    require_platform_admin_step_up()
)

router = APIRouter(
    prefix="/auth/delivery-operations",
    tags=["identity-delivery-operations"],
)


async def get_delivery_operations_runtime(
) -> DeliveryOperationsRuntime:
    try:
        return await build_delivery_operations_runtime()
    except DeliveryOperationsRuntimeUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=GENERIC_UNAVAILABLE,
        ) from exc


@router.get(
    "/metrics",
    response_model=(
        DeliveryOperationalMetricsResponseContract
    ),
)
async def delivery_operational_metrics(
    request: Request,
    current_user: dict = Depends(
        platform_admin_step_up_dependency
    ),
    runtime: DeliveryOperationsRuntime = Depends(
        get_delivery_operations_runtime
    ),
) -> DeliveryOperationalMetricsResponseContract:
    del current_user

    try:
        metrics = await runtime.service.metrics()
    except Exception as exc:
        logger.exception(
            "identity_delivery_metrics_failed",
            extra={
                "request_id": getattr(
                    request.state,
                    "request_id",
                    "unavailable",
                )
            },
        )
        raise HTTPException(
            status_code=503,
            detail=GENERIC_UNAVAILABLE,
        ) from exc

    return DeliveryOperationalMetricsResponseContract(
        pending_count=metrics.pending_count,
        retry_scheduled_count=(
            metrics.retry_scheduled_count
        ),
        leased_count=metrics.leased_count,
        dead_letter_count=metrics.dead_letter_count,
        delivered_count=metrics.delivered_count,
        oldest_pending_age_seconds=(
            metrics.oldest_pending_age_seconds
        ),
    )


@router.post(
    "/dead-letters/{outbox_id}/redrive",
    status_code=202,
    response_model=(
        DeliveryRedriveAcceptedResponseContract
    ),
)
async def redrive_dead_letter_delivery(
    outbox_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(
        platform_admin_step_up_dependency
    ),
    runtime: DeliveryOperationsRuntime = Depends(
        get_delivery_operations_runtime
    ),
) -> JSONResponse:
    del current_user

    try:
        receipt = await runtime.service.redrive(
            outbox_id=outbox_id,
        )
    except DeliveryRedriveUnavailableError:
        # Deliberately preserve non-enumerability of
        # dead-letter row existence and eligibility.
        return JSONResponse(
            status_code=202,
            content=(
                DeliveryRedriveAcceptedResponseContract()
                .model_dump()
            ),
        )
    except Exception:
        logger.exception(
            "identity_delivery_redrive_failed",
            extra={
                "request_id": getattr(
                    request.state,
                    "request_id",
                    "unavailable",
                ),
                "outbox_id": str(outbox_id),
            },
        )
        return JSONResponse(
            status_code=503,
            content={"detail": GENERIC_UNAVAILABLE},
        )

    logger.info(
        "identity_delivery_redrive_accepted",
        extra={
            "request_id": getattr(
                request.state,
                "request_id",
                "unavailable",
            ),
            "outbox_id": str(receipt.outbox_id),
            "preserved_attempt_count": (
                receipt.preserved_attempt_count
            ),
        },
    )

    return JSONResponse(
        status_code=202,
        content=(
            DeliveryRedriveAcceptedResponseContract()
            .model_dump()
        ),
    )


__all__ = [
    "GENERIC_UNAVAILABLE",
    "get_delivery_operations_runtime",
    "platform_admin_step_up_dependency",
    "router",
]
