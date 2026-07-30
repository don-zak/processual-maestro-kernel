from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JourneyState(StrEnum):
    PLAN_SELECTED = "plan_selected"
    REGISTRATION_PENDING = "registration_pending"
    EMAIL_VERIFICATION_PENDING = "email_verification_pending"
    PROFILE_PENDING = "profile_pending"


class JourneyStep(StrEnum):
    ACCOUNT_TYPE = "account_type"
    REGISTRATION = "registration"
    EMAIL_VERIFICATION = "email_verification"
    PROFILE = "profile"


class AccountType(StrEnum):
    INDIVIDUAL = "individual"
    ACADEMIC = "academic"
    ORGANIZATION = "organization"


class BillingCycle(StrEnum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class IntentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(min_length=1, max_length=128)
    source_context: str = Field(default="plan_detail", min_length=1, max_length=64)
    session_token: str = Field(min_length=32, max_length=256)


class IntentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0)
    session_token: str = Field(min_length=32, max_length=256)
    account_type: AccountType | None = None
    billing_cycle: BillingCycle | None = None


class IntentView(BaseModel):
    intent_id: UUID
    plan_id: str
    plan_slug: str
    catalog_version: str
    source_context: str
    billing_cycle: BillingCycle | None
    account_type: AccountType | None
    state: JourneyState
    current_step: JourneyStep
    recovery_action: str
    version: int
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class ResumeView(BaseModel):
    intent: IntentView
    resume_url: str


class IntentClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_token: str = Field(min_length=32, max_length=256)
    version: int = Field(ge=0)


class IntentRegistrationAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_token: str = Field(min_length=32, max_length=256)
    version: int = Field(ge=0)
