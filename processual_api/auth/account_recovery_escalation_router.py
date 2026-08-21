from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.auth.account_recovery_runtime import (
    AccountRecoveryRuntime,
    AccountRecoveryRuntimeUnavailableError,
    build_account_recovery_runtime,
)
from processual_api.auth.rate_limit import (
    ACCOUNT_RECOVERY_START_RULES,
    AuthRateLimitUnavailableError,
    resolve_client_ip,
)
from processual_api.auth.recovery_email_runtime import (
    RecoveryEmailRuntime,
    RecoveryEmailRuntimeUnavailableError,
    build_recovery_email_runtime,
)
from processual_api.auth.recovery_email_verification_service import (
    RecoveryEmailVerificationDeniedError,
)
from processual_api.auth.security import require_platform_admin_step_up
from processual_api.db.session import get_session


class SensitiveRecoveryEscalationAPIRoute(APIRoute):
    def get_route_handler(self):
        route_handler = super().get_route_handler()

        async def sanitized_route_handler(request: Request):
            try:
                return await route_handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=422,
                    content={"detail": "Invalid account recovery escalation request."},
                    headers={"Cache-Control": "no-store"},
                )

        return sanitized_route_handler


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


RecoveryEscalationReason = Literal[
    "lost_recovery_email",
    "lost_authenticator",
    "recovery_codes_unavailable",
    "account_locked",
    "other",
]
RecoveryEscalationResolution = Literal[
    "recovery_channel_reviewed",
    "identity_evidence_insufficient",
    "duplicate",
    "resolved_externally",
]


class AccountRecoveryEscalationCreate(_StrictModel):
    claimed_login: str = Field(min_length=3, max_length=320)
    contact_email: str = Field(min_length=3, max_length=320)
    organization_ref: str | None = Field(default=None, max_length=160)
    reason: RecoveryEscalationReason

    @field_validator("claimed_login", "contact_email")
    @classmethod
    def _looks_like_email(cls, value: str) -> str:
        normalized = value.casefold()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("A valid email-style identifier is required.")
        return normalized


class AccountRecoveryEscalationAccepted(_StrictModel):
    status: str = "accepted"
    request_id: uuid.UUID
    next_action: str = "administrator_review"
    authority_granted: bool = False


class AccountRecoveryEscalationDecision(_StrictModel):
    state: Literal["resolved", "rejected"]
    resolution: RecoveryEscalationResolution


class AccountRecoveryEscalationDecisionResult(_StrictModel):
    status: str = "processed"
    request_id: uuid.UUID
    state: Literal["resolved", "rejected"]
    authority_granted: bool = False
    password_reset_performed: bool = False
    mfa_bypassed: bool = False


class AccountRecoveryChannelApprovalResult(_StrictModel):
    status: str = "verification_issued"
    request_id: uuid.UUID
    next_action: str = "verify_recovery_email_then_restart_recovery"
    authority_granted: bool = False
    password_reset_performed: bool = False
    mfa_bypassed: bool = False
    session_created: bool = False


router = APIRouter(tags=["identity-account-recovery-escalation"], route_class=SensitiveRecoveryEscalationAPIRoute)
platform_admin_step_up_dependency = require_platform_admin_step_up()


async def get_account_recovery_escalation_runtime() -> AccountRecoveryRuntime:
    try:
        return await build_account_recovery_runtime()
    except AccountRecoveryRuntimeUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Account recovery escalation service temporarily unavailable.") from exc


async def get_recovery_channel_runtime() -> RecoveryEmailRuntime:
    try:
        return await build_recovery_email_runtime()
    except RecoveryEmailRuntimeUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Recovery channel replacement service temporarily unavailable.") from exc


def _client_ip(request: Request, runtime: AccountRecoveryRuntime) -> str:
    peer_ip = request.client.host if request.client else ""
    return resolve_client_ip(
        peer_ip=peer_ip,
        forwarded_for=request.headers.get("X-Forwarded-For"),
        policy=runtime.proxy_policy,
    )


@router.post("/escalations", status_code=status.HTTP_202_ACCEPTED, response_model=AccountRecoveryEscalationAccepted)
async def create_account_recovery_escalation(
    request: Request,
    payload: AccountRecoveryEscalationCreate,
    session: AsyncSession = Depends(get_session),
    runtime: AccountRecoveryRuntime = Depends(get_account_recovery_escalation_runtime),
) -> AccountRecoveryEscalationAccepted | JSONResponse:
    try:
        decision = await runtime.rate_limiter.consume(
            action="account_recovery_escalation",
            subjects={"ip": _client_ip(request, runtime), "login": payload.claimed_login},
            rules=ACCOUNT_RECOVERY_START_RULES,
        )
    except (AuthRateLimitUnavailableError, ValueError):
        return JSONResponse(status_code=503, content={"detail": "Account recovery escalation service temporarily unavailable."}, headers={"Cache-Control": "no-store"})
    if not decision.allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Account recovery escalation request rate limit exceeded."},
            headers={"Cache-Control": "no-store", "Retry-After": str(max(1, decision.retry_after_seconds))},
        )

    request_id = uuid.uuid4()
    await session.execute(
        text("""
            INSERT INTO auth_account_recovery_escalations
                (id, claimed_login, contact_email, organization_ref, reason, state, created_at)
            VALUES
                (:id, :claimed_login, :contact_email, :organization_ref, :reason, 'pending', CURRENT_TIMESTAMP)
        """),
        {
            "id": str(request_id),
            "claimed_login": payload.claimed_login,
            "contact_email": payload.contact_email,
            "organization_ref": payload.organization_ref or None,
            "reason": payload.reason,
        },
    )
    await session.commit()
    return AccountRecoveryEscalationAccepted(request_id=request_id)


@router.get("/escalations")
async def list_account_recovery_escalations(
    state: Literal["pending", "resolved", "rejected"] = "pending",
    _current_user: dict = Depends(platform_admin_step_up_dependency),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = (
        await session.execute(
            text("""
                SELECT id, claimed_login, contact_email, organization_ref, reason, state,
                       created_at, reviewed_at, resolution
                  FROM auth_account_recovery_escalations
                 WHERE state = :state
                 ORDER BY created_at ASC
                 LIMIT 200
            """),
            {"state": state},
        )
    ).mappings().all()
    return {
        "state": state,
        "requests": [
            {
                "id": str(row["id"]),
                "claimed_login": row["claimed_login"],
                "contact_email": row["contact_email"],
                "organization_ref": row["organization_ref"],
                "reason": row["reason"],
                "state": row["state"],
                "created_at": row["created_at"],
                "reviewed_at": row["reviewed_at"],
                "resolution": row["resolution"],
            }
            for row in rows
        ],
        "authority_granted": False,
    }


@router.post("/escalations/{request_id}/approve-recovery-channel", response_model=AccountRecoveryChannelApprovalResult)
async def approve_recovery_channel(
    request_id: uuid.UUID,
    current_user: dict = Depends(platform_admin_step_up_dependency),
    session: AsyncSession = Depends(get_session),
    recovery_runtime: RecoveryEmailRuntime = Depends(get_recovery_channel_runtime),
) -> AccountRecoveryChannelApprovalResult:
    try:
        reviewer_id = uuid.UUID(str(current_user["user_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Platform administrator identity required.") from exc

    row = (
        await session.execute(
            text("""
                SELECT id, claimed_login, contact_email, state
                  FROM auth_account_recovery_escalations
                 WHERE id = :id
            """),
            {"id": str(request_id)},
        )
    ).mappings().one_or_none()
    if row is None or row["state"] != "pending":
        await session.rollback()
        raise HTTPException(status_code=409, detail="Recovery escalation is not pending.")

    try:
        await recovery_runtime.service.issue_for_target(
            actor_user_id=reviewer_id,
            target_login=str(row["claimed_login"]),
            recovery_email=str(row["contact_email"]),
            recent_step_up=True,
        )
    except RecoveryEmailVerificationDeniedError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Recovery channel replacement could not be approved.") from exc

    result = await session.execute(
        text("""
            UPDATE auth_account_recovery_escalations
               SET state = 'resolved',
                   resolution = 'recovery_channel_reviewed',
                   reviewed_by_user_id = :reviewed_by_user_id,
                   reviewed_at = CURRENT_TIMESTAMP
             WHERE id = :id
               AND state = 'pending'
        """),
        {"id": str(request_id), "reviewed_by_user_id": str(reviewer_id)},
    )
    if result.rowcount != 1:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Recovery escalation is not pending.")
    await session.commit()
    return AccountRecoveryChannelApprovalResult(request_id=request_id)


@router.post("/escalations/{request_id}/decision", response_model=AccountRecoveryEscalationDecisionResult)
async def decide_account_recovery_escalation(
    request_id: uuid.UUID,
    payload: AccountRecoveryEscalationDecision,
    current_user: dict = Depends(platform_admin_step_up_dependency),
    session: AsyncSession = Depends(get_session),
) -> AccountRecoveryEscalationDecisionResult:
    if payload.state == "resolved" and payload.resolution == "recovery_channel_reviewed":
        raise HTTPException(status_code=400, detail="Use the governed recovery-channel approval action.")
    try:
        reviewer_id = uuid.UUID(str(current_user["user_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Platform administrator identity required.") from exc

    result = await session.execute(
        text("""
            UPDATE auth_account_recovery_escalations
               SET state = :state,
                   resolution = :resolution,
                   reviewed_by_user_id = :reviewed_by_user_id,
                   reviewed_at = CURRENT_TIMESTAMP
             WHERE id = :id
               AND state = 'pending'
        """),
        {
            "id": str(request_id),
            "state": payload.state,
            "resolution": payload.resolution,
            "reviewed_by_user_id": str(reviewer_id),
        },
    )
    if result.rowcount != 1:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Recovery escalation is not pending.")
    await session.commit()
    return AccountRecoveryEscalationDecisionResult(request_id=request_id, state=payload.state)


__all__ = [
    "AccountRecoveryChannelApprovalResult",
    "AccountRecoveryEscalationAccepted",
    "AccountRecoveryEscalationCreate",
    "AccountRecoveryEscalationDecision",
    "AccountRecoveryEscalationDecisionResult",
    "get_account_recovery_escalation_runtime",
    "get_recovery_channel_runtime",
    "platform_admin_step_up_dependency",
    "router",
]
