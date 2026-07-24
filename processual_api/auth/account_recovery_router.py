from __future__ import annotations

import asyncio
import logging
import time

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from processual_api.auth.account_recovery_http_contracts import (
    AccountRecoveryCompletedResponseContract,
    AccountRecoveryCompleteRequestContract,
    AccountRecoveryRevocationResponseContract,
    AccountRecoveryStartAcceptedResponseContract,
    AccountRecoveryStartRequestContract,
    AccountRecoveryVerifiedResponseContract,
    AccountRecoveryVerifyRequestContract,
)
from processual_api.auth.account_recovery_runtime import (
    AccountRecoveryRuntime,
    AccountRecoveryRuntimeUnavailableError,
    build_account_recovery_runtime,
)
from processual_api.auth.account_recovery_service import (
    AccountRecoveryDeniedError,
)
from processual_api.auth.rate_limit import (
    ACCOUNT_RECOVERY_START_RULES,
    ACCOUNT_RECOVERY_VERIFY_RULES,
    AuthRateLimitRule,
    AuthRateLimitUnavailableError,
    resolve_client_ip,
)

logger = logging.getLogger(__name__)

GENERIC_UNAVAILABLE = "Account recovery service temporarily unavailable."
GENERIC_INVALID = "Invalid account recovery request."
GENERIC_DENIED = "Account recovery verification is unavailable."
GENERIC_COMPLETION_DENIED = "Account recovery completion is unavailable."
GENERIC_LIMITED = "Account recovery request rate limit exceeded."


class SensitiveAccountRecoveryAPIRoute(APIRoute):
    def get_route_handler(self):
        route_handler = super().get_route_handler()

        async def sanitized_route_handler(
            request: Request,
        ):
            try:
                return await route_handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=422,
                    content={"detail": GENERIC_INVALID},
                )

        return sanitized_route_handler


router = APIRouter(
    prefix="/auth/account-recovery",
    tags=["identity-account-recovery"],
    route_class=SensitiveAccountRecoveryAPIRoute,
)


async def get_account_recovery_runtime() -> AccountRecoveryRuntime:
    try:
        return await build_account_recovery_runtime()
    except AccountRecoveryRuntimeUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=GENERIC_UNAVAILABLE,
        ) from exc


def _client_ip(
    request: Request,
    runtime: AccountRecoveryRuntime,
) -> str:
    peer_ip = request.client.host if request.client else ""

    return resolve_client_ip(
        peer_ip=peer_ip,
        forwarded_for=request.headers.get("X-Forwarded-For"),
        policy=runtime.proxy_policy,
    )


async def _response_floor(
    started_at: float,
    minimum_seconds: float,
) -> None:
    remaining = minimum_seconds - (time.perf_counter() - started_at)

    if remaining > 0:
        await asyncio.sleep(remaining)


def _rules_for_dimension(
    rules: tuple[AuthRateLimitRule, ...],
    dimension: str,
) -> tuple[AuthRateLimitRule, ...]:
    return tuple(rule for rule in rules if rule.dimension == dimension)


async def _consume(
    *,
    runtime: AccountRecoveryRuntime,
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
        headers={"Retry-After": str(max(1, decision.retry_after_seconds))},
    )


@router.post(
    "/start",
    status_code=202,
    response_model=(AccountRecoveryStartAcceptedResponseContract),
)
async def start_account_recovery(
    request: Request,
    payload: AccountRecoveryStartRequestContract,
    runtime: AccountRecoveryRuntime = Depends(get_account_recovery_runtime),
) -> JSONResponse:
    started_at = time.perf_counter()
    safe_response = AccountRecoveryStartAcceptedResponseContract().model_dump()

    limited = await _consume(
        runtime=runtime,
        action="account_recovery_start",
        subjects={
            "ip": _client_ip(request, runtime),
        },
        rules=_rules_for_dimension(
            ACCOUNT_RECOVERY_START_RULES,
            "ip",
        ),
    )

    if limited is not None:
        await _response_floor(
            started_at,
            runtime.minimum_response_seconds,
        )
        return limited

    try:
        login_decision = await runtime.rate_limiter.consume(
            action="account_recovery_start",
            subjects={"login": payload.login},
            rules=_rules_for_dimension(
                ACCOUNT_RECOVERY_START_RULES,
                "login",
            ),
        )
    except (
        AuthRateLimitUnavailableError,
        ValueError,
    ):
        return JSONResponse(
            status_code=503,
            content={"detail": GENERIC_UNAVAILABLE},
        )

    if login_decision.allowed:
        try:
            await runtime.service.start(login=payload.login)
        except ValueError:
            # Malformed and unknown principals remain
            # externally indistinguishable.
            pass
        except Exception:
            logger.exception(
                "identity_account_recovery_start_failed",
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
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        },
    )


@router.post(
    "/verify",
    status_code=200,
    response_model=(AccountRecoveryVerifiedResponseContract),
)
async def verify_account_recovery(
    request: Request,
    payload: AccountRecoveryVerifyRequestContract,
    runtime: AccountRecoveryRuntime = Depends(get_account_recovery_runtime),
) -> JSONResponse:
    started_at = time.perf_counter()

    limited = await _consume(
        runtime=runtime,
        action="account_recovery_verify",
        subjects={
            "ip": _client_ip(request, runtime),
            "token": payload.token,
        },
        rules=ACCOUNT_RECOVERY_VERIFY_RULES,
    )

    if limited is not None:
        await _response_floor(
            started_at,
            runtime.minimum_response_seconds,
        )
        return limited

    try:
        receipt = await runtime.service.verify(
            request_id=payload.request_id,
            raw_token=payload.token,
        )
    except AccountRecoveryDeniedError:
        await _response_floor(
            started_at,
            runtime.minimum_response_seconds,
        )

        return JSONResponse(
            status_code=400,
            content={"detail": GENERIC_DENIED},
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )
    except Exception:
        logger.exception(
            "identity_account_recovery_verify_failed",
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

    response = AccountRecoveryVerifiedResponseContract(
        request_id=receipt.request_id,
        completion_token=receipt.completion_token,
        completion_expires_at=(receipt.completion_expires_at),
        password_change_required=(receipt.password_change_required),
        mfa_reenrollment_required=(receipt.mfa_reenrollment_required),
        session_created=receipt.session_created,
        access_token_issued=(receipt.access_token_issued),
        refresh_token_issued=(receipt.refresh_token_issued),
    )

    return JSONResponse(
        status_code=200,
        content=response.model_dump(mode="json"),
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        },
    )


@router.post(
    "/complete",
    status_code=200,
    response_model=(AccountRecoveryCompletedResponseContract),
)
async def complete_account_recovery(
    request: Request,
    payload: AccountRecoveryCompleteRequestContract,
    runtime: AccountRecoveryRuntime = Depends(get_account_recovery_runtime),
) -> JSONResponse:
    started_at = time.perf_counter()

    limited = await _consume(
        runtime=runtime,
        action="account_recovery_complete",
        subjects={
            "ip": _client_ip(request, runtime),
            "token": payload.completion_token,
        },
        rules=ACCOUNT_RECOVERY_VERIFY_RULES,
    )

    if limited is not None:
        await _response_floor(
            started_at,
            runtime.minimum_response_seconds,
        )
        return limited

    try:
        receipt = await runtime.service.complete(
            request_id=payload.request_id,
            raw_completion_token=(payload.completion_token),
            new_password=payload.new_password,
        )
    except AccountRecoveryDeniedError:
        await _response_floor(
            started_at,
            runtime.minimum_response_seconds,
        )

        return JSONResponse(
            status_code=400,
            content={"detail": GENERIC_COMPLETION_DENIED},
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )
    except Exception:
        logger.exception(
            "identity_account_recovery_complete_failed",
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
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )

    await _response_floor(
        started_at,
        runtime.minimum_response_seconds,
    )

    response = AccountRecoveryCompletedResponseContract(
        request_id=receipt.request_id,
        completed_at=receipt.completed_at,
        password_changed=receipt.password_changed,
        mfa_reenrollment_required=(receipt.mfa_reenrollment_required),
        revocations=(
            AccountRecoveryRevocationResponseContract(
                sessions_revoked=(receipt.sessions_revoked),
                refresh_tokens_revoked=(receipt.refresh_tokens_revoked),
                action_tokens_revoked=(receipt.action_tokens_revoked),
                supervisor_session_keys_revoked=(receipt.supervisor_session_keys_revoked),
                api_keys_revoked=(receipt.api_keys_revoked),
            )
        ),
        session_created=receipt.session_created,
        access_token_issued=(receipt.access_token_issued),
        refresh_token_issued=(receipt.refresh_token_issued),
        api_key_issued=receipt.api_key_issued,
        authority_granted=receipt.authority_granted,
    )

    return JSONResponse(
        status_code=200,
        content=response.model_dump(mode="json"),
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        },
    )


__all__ = [
    "get_account_recovery_runtime",
    "router",
]
