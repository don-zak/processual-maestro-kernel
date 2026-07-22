from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from processual_api.auth.normalization import normalize_email
from processual_api.auth.rate_limit import (
    EMAIL_VERIFICATION_RESEND_RULES,
    EMAIL_VERIFICATION_RULES,
    ORGANIZATION_REGISTRATION_RULES,
    REGISTRATION_RULES,
    AuthRateLimitRule,
    AuthRateLimitUnavailableError,
    resolve_client_ip,
)
from processual_api.auth.registration_contracts import (
    EmailVerificationProcessedResponseContract,
    EmailVerificationRequestContract,
    EmailVerificationResendAcceptedResponseContract,
    EmailVerificationResendRequestContract,
    IndividualRegistrationRequestContract,
    OrganizationRegistrationRequestContract,
    RegistrationAcceptedResponseContract,
    RegistrationConfigResponseContract,
    RegistrationMode,
)
from processual_api.auth.registration_runtime import (
    RegistrationRuntime,
    RegistrationRuntimeUnavailableError,
    build_registration_runtime,
)
from processual_api.auth.registration_service import RegistrationCommand

logger = logging.getLogger(__name__)
GENERIC_UNAVAILABLE = "Registration service temporarily unavailable."
GENERIC_INVALID = "Invalid registration request."


class SensitiveRequestAPIRoute(APIRoute):
    """Prevent validation responses from reflecting passwords or other inputs."""

    def get_route_handler(self):
        route_handler = super().get_route_handler()

        async def sanitized_route_handler(request: Request):
            try:
                return await route_handler(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"detail": GENERIC_INVALID})

        return sanitized_route_handler


router = APIRouter(
    prefix="/auth",
    tags=["identity-registration"],
    route_class=SensitiveRequestAPIRoute,
)


async def get_registration_runtime() -> RegistrationRuntime:
    try:
        return await build_registration_runtime()
    except RegistrationRuntimeUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc


def _rules_for_dimension(
    rules: Sequence[AuthRateLimitRule],
    dimension: str,
) -> tuple[AuthRateLimitRule, ...]:
    return tuple(rule for rule in rules if rule.dimension == dimension)


async def _response_floor(started_at: float, minimum_seconds: float) -> None:
    remaining = minimum_seconds - (time.perf_counter() - started_at)
    if remaining > 0:
        await asyncio.sleep(remaining)


def _audit(request: Request, *, mode: RegistrationMode, result: str) -> None:
    logger.info(
        "identity_registration",
        extra={
            "request_id": getattr(request.state, "request_id", "unavailable"),
            "registration_mode": mode.value,
            "registration_result": result,
        },
    )


def _verification_audit(request: Request, *, action: str, result: str) -> None:
    logger.info(
        "identity_email_verification",
        extra={
            "request_id": getattr(request.state, "request_id", "unavailable"),
            "verification_action": action,
            "verification_result": result,
        },
    )


def _client_ip(request: Request, runtime: RegistrationRuntime) -> str:
    peer_ip = request.client.host if request.client else ""
    return resolve_client_ip(
        peer_ip=peer_ip,
        forwarded_for=request.headers.get("X-Forwarded-For"),
        policy=runtime.proxy_policy,
    )


async def _register(
    *,
    request: Request,
    payload: IndividualRegistrationRequestContract | OrganizationRegistrationRequestContract,
    mode: RegistrationMode,
    rules: Sequence[AuthRateLimitRule],
    runtime: RegistrationRuntime,
) -> JSONResponse:
    started_at = time.perf_counter()
    peer_ip = request.client.host if request.client else ""
    try:
        client_ip = resolve_client_ip(
            peer_ip=peer_ip,
            forwarded_for=request.headers.get("X-Forwarded-For"),
            policy=runtime.proxy_policy,
        )
        ip_decision = await runtime.rate_limiter.consume(
            action=f"register_{mode.value}",
            subjects={"ip": client_ip},
            rules=_rules_for_dimension(rules, "ip"),
        )
    except AuthRateLimitUnavailableError, ValueError:
        _audit(request, mode=mode, result="authority_unavailable")
        return JSONResponse(status_code=503, content={"detail": GENERIC_UNAVAILABLE})

    if not ip_decision.allowed:
        await _response_floor(started_at, runtime.minimum_response_seconds)
        _audit(request, mode=mode, result="ip_limited")
        return JSONResponse(
            status_code=429,
            content={"detail": "Registration rate limit exceeded."},
            headers={"Retry-After": str(max(1, ip_decision.retry_after_seconds))},
        )

    try:
        normalized_email = normalize_email(payload.email)
    except ValueError:
        await _response_floor(started_at, runtime.minimum_response_seconds)
        _audit(request, mode=mode, result="invalid")
        return JSONResponse(status_code=422, content={"detail": GENERIC_INVALID})

    try:
        email_decision = await runtime.rate_limiter.consume(
            action=f"register_{mode.value}",
            subjects={"email": normalized_email},
            rules=_rules_for_dimension(rules, "email"),
        )
    except AuthRateLimitUnavailableError:
        _audit(request, mode=mode, result="authority_unavailable")
        return JSONResponse(status_code=503, content={"detail": GENERIC_UNAVAILABLE})

    safe_response = RegistrationAcceptedResponseContract().model_dump()
    if not email_decision.allowed:
        await _response_floor(started_at, runtime.minimum_response_seconds)
        _audit(request, mode=mode, result="accepted")
        return JSONResponse(status_code=202, content=safe_response)

    organization_name = (
        payload.organization_name if isinstance(payload, OrganizationRegistrationRequestContract) else None
    )
    try:
        await runtime.service.register(
            RegistrationCommand(
                mode=mode,
                email=normalized_email,
                display_name=payload.full_name,
                password=payload.password,
                accepted_terms_version=payload.accepted_terms_version,
                organization_name=organization_name,
            )
        )
    except ValueError:
        await _response_floor(started_at, runtime.minimum_response_seconds)
        _audit(request, mode=mode, result="invalid")
        return JSONResponse(status_code=422, content={"detail": GENERIC_INVALID})
    except Exception:
        logger.error(
            "identity_registration_authority_failed",
            extra={
                "request_id": getattr(request.state, "request_id", "unavailable"),
                "registration_mode": mode.value,
            },
        )
        _audit(request, mode=mode, result="authority_unavailable")
        return JSONResponse(status_code=503, content={"detail": GENERIC_UNAVAILABLE})

    await _response_floor(started_at, runtime.minimum_response_seconds)
    _audit(request, mode=mode, result="accepted")
    return JSONResponse(status_code=202, content=safe_response)


@router.get(
    "/registration/config",
    response_model=RegistrationConfigResponseContract,
)
async def registration_config() -> RegistrationConfigResponseContract:
    return RegistrationConfigResponseContract()


@router.post(
    "/register",
    status_code=202,
    response_model=RegistrationAcceptedResponseContract,
)
async def register_individual(
    request: Request,
    payload: IndividualRegistrationRequestContract,
    runtime: RegistrationRuntime = Depends(get_registration_runtime),
) -> JSONResponse:
    return await _register(
        request=request,
        payload=payload,
        mode=RegistrationMode.INDIVIDUAL,
        rules=REGISTRATION_RULES,
        runtime=runtime,
    )


@router.post(
    "/register/organization",
    status_code=202,
    response_model=RegistrationAcceptedResponseContract,
)
async def register_organization(
    request: Request,
    payload: OrganizationRegistrationRequestContract,
    runtime: RegistrationRuntime = Depends(get_registration_runtime),
) -> JSONResponse:
    return await _register(
        request=request,
        payload=payload,
        mode=RegistrationMode.ORGANIZATION,
        rules=ORGANIZATION_REGISTRATION_RULES,
        runtime=runtime,
    )


@router.post(
    "/verify-email",
    response_model=EmailVerificationProcessedResponseContract,
)
async def verify_email(
    request: Request,
    payload: EmailVerificationRequestContract,
    runtime: RegistrationRuntime = Depends(get_registration_runtime),
) -> JSONResponse:
    started_at = time.perf_counter()
    safe_response = EmailVerificationProcessedResponseContract().model_dump()
    try:
        decision = await runtime.rate_limiter.consume(
            action="verify_email",
            subjects={"ip": _client_ip(request, runtime), "token": payload.token},
            rules=EMAIL_VERIFICATION_RULES,
        )
    except AuthRateLimitUnavailableError, ValueError:
        _verification_audit(request, action="verify", result="authority_unavailable")
        return JSONResponse(status_code=503, content={"detail": GENERIC_UNAVAILABLE})
    if not decision.allowed:
        await _response_floor(started_at, runtime.minimum_response_seconds)
        _verification_audit(request, action="verify", result="limited")
        return JSONResponse(
            status_code=429,
            content={"detail": "Verification rate limit exceeded."},
            headers={"Retry-After": str(max(1, decision.retry_after_seconds))},
        )
    verification_service = runtime.email_verification_service
    if verification_service is None:
        _verification_audit(request, action="verify", result="authority_unavailable")
        return JSONResponse(status_code=503, content={"detail": GENERIC_UNAVAILABLE})
    try:
        await verification_service.verify(payload.token)
    except Exception:
        logger.error(
            "identity_email_verification_authority_failed",
            extra={"request_id": getattr(request.state, "request_id", "unavailable")},
        )
        _verification_audit(request, action="verify", result="authority_unavailable")
        return JSONResponse(status_code=503, content={"detail": GENERIC_UNAVAILABLE})
    await _response_floor(started_at, runtime.minimum_response_seconds)
    _verification_audit(request, action="verify", result="processed")
    return JSONResponse(status_code=200, content=safe_response)


@router.post(
    "/verification/resend",
    status_code=202,
    response_model=EmailVerificationResendAcceptedResponseContract,
)
async def resend_email_verification(
    request: Request,
    payload: EmailVerificationResendRequestContract,
    runtime: RegistrationRuntime = Depends(get_registration_runtime),
) -> JSONResponse:
    started_at = time.perf_counter()
    safe_response = EmailVerificationResendAcceptedResponseContract().model_dump()
    try:
        client_ip = _client_ip(request, runtime)
        ip_decision = await runtime.rate_limiter.consume(
            action="resend_email_verification",
            subjects={"ip": client_ip},
            rules=_rules_for_dimension(EMAIL_VERIFICATION_RESEND_RULES, "ip"),
        )
    except AuthRateLimitUnavailableError, ValueError:
        _verification_audit(request, action="resend", result="authority_unavailable")
        return JSONResponse(status_code=503, content={"detail": GENERIC_UNAVAILABLE})
    if not ip_decision.allowed:
        await _response_floor(started_at, runtime.minimum_response_seconds)
        _verification_audit(request, action="resend", result="ip_limited")
        return JSONResponse(
            status_code=429,
            content={"detail": "Verification rate limit exceeded."},
            headers={"Retry-After": str(max(1, ip_decision.retry_after_seconds))},
        )
    try:
        normalized_email = normalize_email(payload.email)
        email_decision = await runtime.rate_limiter.consume(
            action="resend_email_verification",
            subjects={"email": normalized_email},
            rules=_rules_for_dimension(EMAIL_VERIFICATION_RESEND_RULES, "email"),
        )
    except ValueError:
        await _response_floor(started_at, runtime.minimum_response_seconds)
        _verification_audit(request, action="resend", result="accepted")
        return JSONResponse(status_code=202, content=safe_response)
    except AuthRateLimitUnavailableError:
        _verification_audit(request, action="resend", result="authority_unavailable")
        return JSONResponse(status_code=503, content={"detail": GENERIC_UNAVAILABLE})
    if not email_decision.allowed:
        await _response_floor(started_at, runtime.minimum_response_seconds)
        _verification_audit(request, action="resend", result="accepted")
        return JSONResponse(status_code=202, content=safe_response)
    verification_service = runtime.email_verification_service
    if verification_service is None:
        _verification_audit(request, action="resend", result="authority_unavailable")
        return JSONResponse(status_code=503, content={"detail": GENERIC_UNAVAILABLE})
    try:
        await verification_service.resend(normalized_email)
    except Exception:
        logger.error(
            "identity_email_verification_resend_authority_failed",
            extra={"request_id": getattr(request.state, "request_id", "unavailable")},
        )
        _verification_audit(request, action="resend", result="authority_unavailable")
        return JSONResponse(status_code=503, content={"detail": GENERIC_UNAVAILABLE})
    await _response_floor(started_at, runtime.minimum_response_seconds)
    _verification_audit(request, action="resend", result="accepted")
    return JSONResponse(status_code=202, content=safe_response)


__all__ = ["get_registration_runtime", "router"]
