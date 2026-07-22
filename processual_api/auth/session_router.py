from __future__ import annotations

import asyncio
import logging
import secrets
import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from processual_api.auth.normalization import normalize_email
from processual_api.auth.rate_limit import (
    LOGIN_RULES,
    SESSION_REFRESH_RULES,
    AuthRateLimitUnavailableError,
    AuthRateLimitRule,
    resolve_client_ip,
)
from processual_api.auth.security import get_current_user
from processual_api.auth.session_contracts import (
    AccessTokenResponseContract,
    IssuedSession,
    LoginRequestContract,
    SessionListResponseContract,
    SessionProcessedResponseContract,
    SessionViewContract,
)
from processual_api.auth.session_runtime import (
    SessionRuntime,
    SessionRuntimeUnavailableError,
    build_session_runtime,
)
from processual_api.auth.session_service import (
    InvalidSessionCredentialsError,
    RefreshTokenReuseError,
    SessionAuthorityUnavailableError,
)

logger = logging.getLogger(__name__)
REFRESH_COOKIE = "pmk_refresh_token"
CSRF_COOKIE = "pmk_csrf_token"
CSRF_HEADER = "X-CSRF-Token"
GENERIC_INVALID = "Invalid session credentials."
GENERIC_UNAVAILABLE = "Session service temporarily unavailable."


class SensitiveSessionAPIRoute(APIRoute):
    def get_route_handler(self):
        route_handler = super().get_route_handler()

        async def sanitized_route_handler(request: Request):
            try:
                return await route_handler(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"detail": "Invalid session request."})

        return sanitized_route_handler


router = APIRouter(
    prefix="/auth",
    tags=["identity-sessions"],
    route_class=SensitiveSessionAPIRoute,
)


async def get_session_runtime() -> SessionRuntime:
    try:
        return await build_session_runtime()
    except SessionRuntimeUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc


async def get_identity_user(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("session_type") != "identity_user":
        raise HTTPException(status_code=403, detail="Identity session required.")
    return current_user


def _audit(request: Request, *, action: str, result: str) -> None:
    logger.info(
        "identity_session",
        extra={
            "request_id": getattr(request.state, "request_id", "unavailable"),
            "session_action": action,
            "session_result": result,
        },
    )


def _client_ip(request: Request, runtime: SessionRuntime) -> str:
    peer_ip = request.client.host if request.client is not None else "127.0.0.1"
    return resolve_client_ip(
        peer_ip=peer_ip,
        forwarded_for=request.headers.get("X-Forwarded-For"),
        policy=runtime.proxy_policy,
    )


async def _consume_rate_limit(
    *,
    request: Request,
    runtime: SessionRuntime,
    action: str,
    rules: tuple[AuthRateLimitRule, ...],
    subjects: dict[str, str],
) -> None:
    try:
        decision = await runtime.rate_limiter.consume(
            action=action,
            subjects=subjects,
            rules=rules,
        )
    except (AuthRateLimitUnavailableError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many session requests.",
            headers={"Retry-After": str(max(1, decision.retry_after_seconds))},
        )


async def _response_floor(started_at: float, minimum_seconds: float) -> None:
    remaining = minimum_seconds - (time.perf_counter() - started_at)
    if remaining > 0:
        await asyncio.sleep(remaining)


def _set_session_cookies(response: Response, issued: IssuedSession) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        issued.refresh_token,
        max_age=issued.refresh_expires_in,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/auth/session",
    )
    response.set_cookie(
        CSRF_COOKIE,
        issued.csrf_token,
        max_age=issued.refresh_expires_in,
        secure=True,
        httponly=False,
        samesite="strict",
        path="/auth/session",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/auth/session", secure=True, httponly=True, samesite="strict")
    response.delete_cookie(CSRF_COOKIE, path="/auth/session", secure=True, httponly=False, samesite="strict")
    response.headers["Cache-Control"] = "no-store"


def _refresh_credentials(request: Request, csrf_header: str | None) -> tuple[str, str]:
    refresh_token = request.cookies.get(REFRESH_COOKIE, "")
    csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
    supplied = csrf_header or ""
    if not refresh_token or not csrf_cookie or not supplied or not secrets.compare_digest(csrf_cookie, supplied):
        raise HTTPException(status_code=403, detail="Session request denied.")
    return refresh_token, csrf_cookie


@router.post("/login", response_model=AccessTokenResponseContract)
async def login(
    body: LoginRequestContract,
    request: Request,
    response: Response,
    runtime: SessionRuntime = Depends(get_session_runtime),
):
    started_at = time.perf_counter()
    try:
        try:
            email_subject = normalize_email(body.email)
        except ValueError:
            email_subject = "invalid-email"
        await _consume_rate_limit(
            request=request,
            runtime=runtime,
            action="login",
            rules=LOGIN_RULES,
            subjects={"ip": _client_ip(request, runtime), "email": email_subject},
        )
        issued = await runtime.service.login(email=body.email, password=body.password)
    except InvalidSessionCredentialsError as exc:
        _audit(request, action="login", result="denied")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_INVALID,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except SessionAuthorityUnavailableError as exc:
        _audit(request, action="login", result="unavailable")
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    finally:
        await _response_floor(started_at, runtime.minimum_response_seconds)
    _set_session_cookies(response, issued)
    _audit(request, action="login", result="accepted")
    return AccessTokenResponseContract(
        access_token=issued.access_token,
        expires_in=issued.access_expires_in,
    )


@router.post("/session/refresh", response_model=AccessTokenResponseContract)
async def refresh_session(
    request: Request,
    response: Response,
    csrf_header: str | None = Header(default=None, alias=CSRF_HEADER),
    runtime: SessionRuntime = Depends(get_session_runtime),
):
    raw_refresh_token, _ = _refresh_credentials(request, csrf_header)
    await _consume_rate_limit(
        request=request,
        runtime=runtime,
        action="session_refresh",
        rules=SESSION_REFRESH_RULES,
        subjects={"ip": _client_ip(request, runtime), "token": raw_refresh_token},
    )
    try:
        issued = await runtime.service.refresh(raw_refresh_token)
    except (InvalidSessionCredentialsError, RefreshTokenReuseError):
        _audit(request, action="refresh", result="denied")
        denied = JSONResponse(status_code=401, content={"detail": GENERIC_INVALID})
        _clear_session_cookies(denied)
        return denied
    except SessionAuthorityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    _set_session_cookies(response, issued)
    _audit(request, action="refresh", result="accepted")
    return AccessTokenResponseContract(
        access_token=issued.access_token,
        expires_in=issued.access_expires_in,
    )


@router.post("/session/logout", response_model=SessionProcessedResponseContract)
async def logout_session(
    request: Request,
    response: Response,
    csrf_header: str | None = Header(default=None, alias=CSRF_HEADER),
    runtime: SessionRuntime = Depends(get_session_runtime),
):
    raw_refresh_token, _ = _refresh_credentials(request, csrf_header)
    try:
        await runtime.service.logout(raw_refresh_token)
    except SessionAuthorityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    _clear_session_cookies(response)
    _audit(request, action="logout", result="processed")
    return SessionProcessedResponseContract()


@router.post("/session/logout-all", response_model=SessionProcessedResponseContract)
async def logout_all_sessions(
    request: Request,
    response: Response,
    csrf_header: str | None = Header(default=None, alias=CSRF_HEADER),
    runtime: SessionRuntime = Depends(get_session_runtime),
):
    raw_refresh_token, _ = _refresh_credentials(request, csrf_header)
    try:
        await runtime.service.logout_all(raw_refresh_token)
    except SessionAuthorityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    _clear_session_cookies(response)
    _audit(request, action="logout_all", result="processed")
    return SessionProcessedResponseContract()


@router.get("/sessions", response_model=SessionListResponseContract)
async def list_sessions(
    runtime: SessionRuntime = Depends(get_session_runtime),
    current_user: dict = Depends(get_identity_user),
):
    try:
        user_id = uuid.UUID(current_user["user_id"])
        current_session_id = uuid.UUID(current_user["session_id"])
        sessions = await runtime.service.list_sessions(user_id)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail=GENERIC_INVALID) from exc
    except SessionAuthorityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    return SessionListResponseContract(
        sessions=tuple(
            SessionViewContract(
                id=session.id,
                authenticated_at=session.authenticated_at,
                last_seen_at=session.last_seen_at,
                expires_at=session.expires_at,
                current=session.id == current_session_id,
            )
            for session in sessions
        )
    )


@router.delete("/sessions/{session_id}", response_model=SessionProcessedResponseContract)
async def revoke_session(
    session_id: uuid.UUID,
    runtime: SessionRuntime = Depends(get_session_runtime),
    current_user: dict = Depends(get_identity_user),
):
    try:
        await runtime.service.revoke_session(
            user_id=uuid.UUID(current_user["user_id"]),
            session_id=session_id,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail=GENERIC_INVALID) from exc
    except SessionAuthorityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    return SessionProcessedResponseContract()


__all__ = ["get_session_runtime", "router"]
