from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from processual_api.auth.mfa_contracts import (
    MfaCodeRequestContract,
    MfaEnrollmentRequestContract,
    MfaEnrollmentResponseContract,
    MfaProcessedResponseContract,
    MfaRecoveryCodesResponseContract,
    MfaStatusResponseContract,
    MfaVerificationRequestContract,
)
from processual_api.auth.mfa_runtime import (
    MfaRuntime,
    MfaRuntimeUnavailableError,
    build_mfa_runtime,
)
from processual_api.auth.mfa_service import (
    InvalidMfaCredentialError,
    MfaAuthorityUnavailableError,
    MfaConflictError,
    MfaStepUpRequiredError,
)
from processual_api.auth.rate_limit import (
    MFA_VERIFICATION_RULES,
    AuthRateLimitUnavailableError,
    resolve_client_ip,
)
from processual_api.auth.session_router import get_identity_user

logger = logging.getLogger(__name__)
GENERIC_INVALID = "Invalid MFA credential."
GENERIC_UNAVAILABLE = "MFA service temporarily unavailable."


class SensitiveMfaAPIRoute(APIRoute):
    def get_route_handler(self):
        route_handler = super().get_route_handler()

        async def sanitized_route_handler(request: Request):
            try:
                return await route_handler(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"detail": "Invalid MFA request."})

        return sanitized_route_handler


router = APIRouter(
    prefix="/auth/mfa",
    tags=["identity-mfa"],
    route_class=SensitiveMfaAPIRoute,
)


async def get_mfa_runtime() -> MfaRuntime:
    try:
        return await build_mfa_runtime()
    except MfaRuntimeUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc


def _principal(current_user: dict) -> tuple[uuid.UUID, uuid.UUID]:
    try:
        return uuid.UUID(current_user["user_id"]), uuid.UUID(current_user["session_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid identity session.") from exc


def _audit(request: Request, *, action: str, result: str) -> None:
    logger.info(
        "identity_mfa",
        extra={
            "request_id": getattr(request.state, "request_id", "unavailable"),
            "mfa_action": action,
            "mfa_result": result,
        },
    )


def _client_ip(request: Request, runtime: MfaRuntime) -> str:
    peer_ip = request.client.host if request.client is not None else "127.0.0.1"
    return resolve_client_ip(
        peer_ip=peer_ip,
        forwarded_for=request.headers.get("X-Forwarded-For"),
        policy=runtime.proxy_policy,
    )


async def _limit_verification(
    request: Request,
    runtime: MfaRuntime,
    *,
    user_id: uuid.UUID,
) -> None:
    try:
        decision = await runtime.rate_limiter.consume(
            action="mfa_verify",
            subjects={"ip": _client_ip(request, runtime), "user": str(user_id)},
            rules=MFA_VERIFICATION_RULES,
        )
    except (AuthRateLimitUnavailableError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many MFA requests.",
            headers={"Retry-After": str(max(1, decision.retry_after_seconds))},
        )


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


@router.get("/status", response_model=MfaStatusResponseContract)
async def mfa_status(
    current_user: dict = Depends(get_identity_user),
    runtime: MfaRuntime = Depends(get_mfa_runtime),
):
    user_id, session_id = _principal(current_user)
    try:
        result = await runtime.service.status(user_id=user_id, session_id=session_id)
    except MfaAuthorityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    return MfaStatusResponseContract(
        enabled=result.enabled,
        pending_enrollment=result.pending_enrollment,
        recovery_codes_remaining=result.recovery_codes_remaining,
        step_up_satisfied=result.step_up_satisfied,
    )


@router.post("/totp/enroll", response_model=MfaEnrollmentResponseContract)
async def enroll_totp(
    body: MfaEnrollmentRequestContract,
    request: Request,
    response: Response,
    current_user: dict = Depends(get_identity_user),
    runtime: MfaRuntime = Depends(get_mfa_runtime),
):
    user_id, _ = _principal(current_user)
    try:
        enrollment = await runtime.service.enroll(user_id=user_id, label=body.label)
    except MfaConflictError as exc:
        raise HTTPException(status_code=409, detail="MFA enrollment is not available.") from exc
    except MfaAuthorityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    _no_store(response)
    _audit(request, action="enroll", result="pending")
    return MfaEnrollmentResponseContract(
        secret=enrollment.secret,
        provisioning_uri=enrollment.provisioning_uri,
    )


@router.post("/totp/confirm", response_model=MfaRecoveryCodesResponseContract)
async def confirm_totp(
    body: MfaCodeRequestContract,
    request: Request,
    response: Response,
    current_user: dict = Depends(get_identity_user),
    runtime: MfaRuntime = Depends(get_mfa_runtime),
):
    user_id, session_id = _principal(current_user)
    await _limit_verification(request, runtime, user_id=user_id)
    try:
        codes = await runtime.service.confirm_enrollment(
            user_id=user_id,
            session_id=session_id,
            code=body.code,
        )
    except InvalidMfaCredentialError as exc:
        _audit(request, action="confirm", result="denied")
        raise HTTPException(status_code=401, detail=GENERIC_INVALID) from exc
    except MfaConflictError as exc:
        raise HTTPException(status_code=409, detail="MFA enrollment is not available.") from exc
    except MfaAuthorityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    _no_store(response)
    _audit(request, action="confirm", result="accepted")
    return MfaRecoveryCodesResponseContract(recovery_codes=codes)


@router.post("/verify", response_model=MfaProcessedResponseContract)
async def verify_mfa(
    body: MfaVerificationRequestContract,
    request: Request,
    response: Response,
    current_user: dict = Depends(get_identity_user),
    runtime: MfaRuntime = Depends(get_mfa_runtime),
):
    user_id, session_id = _principal(current_user)
    await _limit_verification(request, runtime, user_id=user_id)
    try:
        await runtime.service.verify(
            user_id=user_id,
            session_id=session_id,
            code=body.code,
            recovery_code=body.recovery_code,
        )
    except InvalidMfaCredentialError as exc:
        _audit(request, action="verify", result="denied")
        raise HTTPException(status_code=401, detail=GENERIC_INVALID) from exc
    except MfaAuthorityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    _no_store(response)
    _audit(request, action="verify", result="accepted")
    return MfaProcessedResponseContract()


@router.post("/recovery-codes/regenerate", response_model=MfaRecoveryCodesResponseContract)
async def regenerate_recovery_codes(
    request: Request,
    response: Response,
    current_user: dict = Depends(get_identity_user),
    runtime: MfaRuntime = Depends(get_mfa_runtime),
):
    user_id, session_id = _principal(current_user)
    try:
        codes = await runtime.service.regenerate_recovery_codes(
            user_id=user_id,
            session_id=session_id,
        )
    except MfaStepUpRequiredError as exc:
        raise HTTPException(status_code=403, detail="Recent MFA verification required.") from exc
    except MfaConflictError as exc:
        raise HTTPException(status_code=409, detail="MFA recovery codes are not available.") from exc
    except MfaAuthorityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    _no_store(response)
    _audit(request, action="recovery_regenerate", result="accepted")
    return MfaRecoveryCodesResponseContract(recovery_codes=codes)


@router.post("/disable", response_model=MfaProcessedResponseContract)
async def disable_mfa(
    request: Request,
    current_user: dict = Depends(get_identity_user),
    runtime: MfaRuntime = Depends(get_mfa_runtime),
):
    user_id, session_id = _principal(current_user)
    try:
        await runtime.service.disable(user_id=user_id, session_id=session_id)
    except MfaStepUpRequiredError as exc:
        raise HTTPException(status_code=403, detail="Recent MFA verification required.") from exc
    except MfaConflictError as exc:
        raise HTTPException(status_code=409, detail="MFA disable is not available.") from exc
    except MfaAuthorityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    _audit(request, action="disable", result="accepted")
    return MfaProcessedResponseContract()


__all__ = ["get_mfa_runtime", "router"]
