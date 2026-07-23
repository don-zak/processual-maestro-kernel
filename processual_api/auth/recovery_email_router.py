from __future__ import annotations

import asyncio
import logging
import time
import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from processual_api.auth.rate_limit import (
    RECOVERY_EMAIL_ISSUE_RULES,
    RECOVERY_EMAIL_VERIFY_RULES,
    AuthRateLimitRule,
    AuthRateLimitUnavailableError,
    resolve_client_ip,
)
from processual_api.auth.recovery_email_contracts import (
    RecoveryEmailVerificationAcceptedResponseContract,
    RecoveryEmailVerificationProcessedResponseContract,
    RecoveryEmailVerificationRequestContract,
)
from processual_api.auth.recovery_email_runtime import (
    RecoveryEmailRuntime,
    RecoveryEmailRuntimeUnavailableError,
    build_recovery_email_runtime,
)
from processual_api.auth.recovery_email_verification_service import (
    RecoveryEmailVerificationDeniedError,
)
from processual_api.auth.security import (
    require_platform_admin_step_up,
)

logger = logging.getLogger(__name__)

GENERIC_UNAVAILABLE = (
    "Recovery-email service temporarily unavailable."
)
GENERIC_LIMITED = (
    "Recovery-email request rate limit exceeded."
)

class SensitiveRecoveryEmailAPIRoute(APIRoute):
    def get_route_handler(self):
        route_handler = super().get_route_handler()

        async def sanitized_route_handler(request: Request):
            try:
                return await route_handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=422,
                    content={
                        "detail": "Invalid recovery-email request."
                    },
                )

        return sanitized_route_handler


platform_admin_step_up_dependency = (
    require_platform_admin_step_up()
)


router = APIRouter(
    prefix="/auth/recovery-email",
    tags=["identity-recovery-email"],
    route_class=SensitiveRecoveryEmailAPIRoute,
)


async def get_recovery_email_runtime(
) -> RecoveryEmailRuntime:
    try:
        return await build_recovery_email_runtime()
    except RecoveryEmailRuntimeUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=GENERIC_UNAVAILABLE,
        ) from exc


def _client_ip(request: Request, runtime: RecoveryEmailRuntime) -> str:
    peer_ip = request.client.host if request.client else ""
    return resolve_client_ip(
        peer_ip=peer_ip,
        forwarded_for=request.headers.get("X-Forwarded-For"),
        policy=runtime.proxy_policy,
    )


def _principal_user_id(
    current_user: dict,
) -> uuid.UUID:
    try:
        return uuid.UUID(str(current_user["user_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid identity session.",
        ) from exc


async def _response_floor(
    started_at: float,
    minimum_seconds: float,
) -> None:
    remaining = (
        minimum_seconds
        - (time.perf_counter() - started_at)
    )

    if remaining > 0:
        await asyncio.sleep(remaining)


async def _consume_limit(
    *,
    request: Request,
    runtime: RecoveryEmailRuntime,
    action: str,
    subjects: dict[str, str],
    rules: tuple[AuthRateLimitRule, ...],
) -> JSONResponse | None:
    try:
        decision = await runtime.rate_limiter.consume(
            action=action,
            subjects=subjects,
            rules=rules,
        )
    except (
        AuthRateLimitUnavailableError,
        ValueError,
    ):
        return JSONResponse(
            status_code=503,
            content={"detail": GENERIC_UNAVAILABLE},
        )

    if decision.allowed:
        return None

    return JSONResponse(
        status_code=429,
        content={"detail": GENERIC_LIMITED},
        headers={
            "Retry-After": str(
                max(1, decision.retry_after_seconds)
            )
        },
    )


@router.post(
    "/verification",
    status_code=202,
)
async def issue_recovery_email_verification(
    request: Request,
    current_user: dict = Depends(
        platform_admin_step_up_dependency
    ),
    runtime: RecoveryEmailRuntime = Depends(
        get_recovery_email_runtime
    ),
) -> JSONResponse:
    started_at = time.perf_counter()
    safe_response = (
        RecoveryEmailVerificationAcceptedResponseContract()
        .model_dump()
    )
    user_id = _principal_user_id(current_user)

    limited = await _consume_limit(
        request=request,
        runtime=runtime,
        action="recovery_email_issue",
        subjects={
            "ip": _client_ip(request, runtime),
            "user": str(user_id),
        },
        rules=RECOVERY_EMAIL_ISSUE_RULES,
    )

    if limited is not None:
        await _response_floor(
            started_at,
            runtime.minimum_response_seconds,
        )
        return limited

    try:
        await runtime.service.issue(
            actor_user_id=user_id,
            recent_step_up=True,
        )
    except RecoveryEmailVerificationDeniedError:
        # Keep pending-email presence and state non-enumerable.
        pass
    except Exception:
        logger.exception(
            "identity_recovery_email_issue_failed",
            extra={
                "request_id": getattr(
                    request.state,
                    "request_id",
                    "unavailable",
                )
            },
        )
        return JSONResponse(
            status_code=503,
            content={"detail": GENERIC_UNAVAILABLE},
        )

    await _response_floor(
        started_at,
        runtime.minimum_response_seconds,
    )

    return JSONResponse(
        status_code=202,
        content=safe_response,
    )


@router.post(
    "/resend",
    status_code=202,
)
async def resend_recovery_email_verification(
    request: Request,
    current_user: dict = Depends(
        platform_admin_step_up_dependency
    ),
    runtime: RecoveryEmailRuntime = Depends(
        get_recovery_email_runtime
    ),
) -> JSONResponse:
    return await issue_recovery_email_verification(
        request=request,
        current_user=current_user,
        runtime=runtime,
    )


@router.post(
    "/verify",
    status_code=200,
)
async def verify_recovery_email(
    request: Request,
    payload: RecoveryEmailVerificationRequestContract,
    runtime: RecoveryEmailRuntime = Depends(
        get_recovery_email_runtime
    ),
) -> JSONResponse:
    started_at = time.perf_counter()
    safe_response = (
        RecoveryEmailVerificationProcessedResponseContract()
        .model_dump()
    )

    limited = await _consume_limit(
        request=request,
        runtime=runtime,
        action="recovery_email_verify",
        subjects={
            "ip": _client_ip(request, runtime),
            "token": payload.token,
        },
        rules=RECOVERY_EMAIL_VERIFY_RULES,
    )

    if limited is not None:
        await _response_floor(
            started_at,
            runtime.minimum_response_seconds,
        )
        return limited

    try:
        await runtime.service.verify(
            raw_token=payload.token
        )
    except RecoveryEmailVerificationDeniedError:
        # Invalid, expired and replayed tokens are deliberately
        # indistinguishable at the HTTP boundary.
        pass
    except Exception:
        logger.exception(
            "identity_recovery_email_verify_failed",
            extra={
                "request_id": getattr(
                    request.state,
                    "request_id",
                    "unavailable",
                )
            },
        )
        return JSONResponse(
            status_code=503,
            content={"detail": GENERIC_UNAVAILABLE},
        )

    await _response_floor(
        started_at,
        runtime.minimum_response_seconds,
    )

    return JSONResponse(
        status_code=200,
        content=safe_response,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        },
    )


__all__ = [
    "get_recovery_email_runtime",
    "platform_admin_step_up_dependency",
    "router",
]
