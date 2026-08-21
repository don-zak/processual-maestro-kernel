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


router = APIRouter(
    tags=["identity-account-recovery-escalation"],
    route_class=SensitiveRecoveryEscalationAPIRoute,
)
platform_admin_step_up_dependency = require_platform_admin_step_up()


@router.post(
    "/escalations",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AccountRecoveryEscalationAccepted,
)
async def create_account_recovery_escalation(
    payload: AccountRecoveryEscalationCreate,
    session: AsyncSession = Depends(get_session),
) -> AccountRecoveryEscalationAccepted:
    request_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO auth_account_recovery_escalations
                (id, claimed_login, contact_email, organization_ref, reason, state, created_at)
            VALUES
                (:id, :claimed_login, :contact_email, :organization_ref, :reason, 'pending', CURRENT_TIMESTAMP)
            """
        ),
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
            text(
                """
                SELECT id, claimed_login, contact_email, organization_ref, reason, state,
                       created_at, reviewed_at, resolution
                  FROM auth_account_recovery_escalations
                 WHERE state = :state
                 ORDER BY created_at ASC
                 LIMIT 200
                """
            ),
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


@router.post(
    "/escalations/{request_id}/decision",
    response_model=AccountRecoveryEscalationDecisionResult,
)
async def decide_account_recovery_escalation(
    request_id: uuid.UUID,
    payload: AccountRecoveryEscalationDecision,
    current_user: dict = Depends(platform_admin_step_up_dependency),
    session: AsyncSession = Depends(get_session),
) -> AccountRecoveryEscalationDecisionResult:
    try:
        reviewer_id = uuid.UUID(str(current_user["user_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Platform administrator identity required.") from exc

    result = await session.execute(
        text(
            """
            UPDATE auth_account_recovery_escalations
               SET state = :state,
                   resolution = :resolution,
                   reviewed_by_user_id = :reviewed_by_user_id,
                   reviewed_at = CURRENT_TIMESTAMP
             WHERE id = :id
               AND state = 'pending'
            """
        ),
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
    return AccountRecoveryEscalationDecisionResult(
        request_id=request_id,
        state=payload.state,
    )


__all__ = [
    "AccountRecoveryEscalationAccepted",
    "AccountRecoveryEscalationCreate",
    "AccountRecoveryEscalationDecision",
    "AccountRecoveryEscalationDecisionResult",
    "platform_admin_step_up_dependency",
    "router",
]
