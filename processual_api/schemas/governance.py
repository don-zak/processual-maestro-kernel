from __future__ import annotations

import uuid
from datetime import datetime

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
