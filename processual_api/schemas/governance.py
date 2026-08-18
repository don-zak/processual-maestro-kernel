from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GovernanceReport(BaseModel):
    workflow_id: str
    runtime_mode: str
    policy: str


class FateReport(BaseModel):
    workflow_id: str
    fate_vector: dict[str, float]
    existence_rank: str


class AdministratorAuthorityResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    user_status: str
    authority: str
    authority_status: str
    granted_at: datetime


class AdministratorGovernanceResponse(BaseModel):
    administrators: tuple[AdministratorAuthorityResponse, ...]
    count: int


class AdministratorInvitationResponse(BaseModel):
    invitation_id: uuid.UUID
    email_normalized: str
    supervision_level: str
    status: str
    invited_by_user_id: uuid.UUID
    invite_reason: str
    expires_at: datetime
    accepted_by_user_id: uuid.UUID | None
    accepted_at: datetime | None
    cancelled_by_user_id: uuid.UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime


class AdministratorInvitationListResponse(BaseModel):
    invitations: tuple[AdministratorInvitationResponse, ...]
    count: int


class AdministratorActivityResponse(BaseModel):
    event_id: uuid.UUID
    event_type: str
    actor_user_id: uuid.UUID | None
    subject_user_id: uuid.UUID
    invitation_id: uuid.UUID | None
    permission: str | None
    reason: str
    occurred_at: datetime


class AdministratorActivityListResponse(BaseModel):
    events: tuple[AdministratorActivityResponse, ...]
    count: int


class AdministratorSessionResponse(BaseModel):
    session_id: uuid.UUID
    user_id: uuid.UUID
    authenticated_at: datetime
    mfa_satisfied_at: datetime | None
    last_seen_at: datetime | None
    expires_at: datetime
    revoked_at: datetime | None
    revoke_reason: str | None


class AdministratorSessionListResponse(BaseModel):
    sessions: tuple[AdministratorSessionResponse, ...]
    count: int


class AdministratorInvitationIssueRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    supervision_level: Literal["operations_supervisor", "review_supervisor"]
    reason: str = Field(min_length=12, max_length=500)
    expires_in_hours: int = Field(default=48, ge=1, le=168)


class AdministratorInvitationIssueResponse(BaseModel):
    invitation_id: uuid.UUID
    delivery_outbox_id: uuid.UUID
    email_normalized: str
    supervision_level: str
    expires_at: datetime
    status: Literal["pending"] = "pending"


class AdministratorInvitationCancellationRequest(BaseModel):
    reason: str = Field(min_length=12, max_length=500)


class AdministratorInvitationCancellationResponse(BaseModel):
    invitation_id: uuid.UUID
    cancelled_by_user_id: uuid.UUID
    cancelled_at: datetime
    status: str


class AdministratorLifecycleRequest(BaseModel):
    reason: str = Field(min_length=12, max_length=500)


class AdministratorLifecycleResponse(BaseModel):
    user_id: uuid.UUID
    status: str
    occurred_at: datetime


class AdministratorSessionRevocationResponse(BaseModel):
    user_id: uuid.UUID
    session_id: uuid.UUID
    revoked_at: datetime
