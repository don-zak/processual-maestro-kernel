"""Runtime-neutral identity and registration contracts.

This module fixes the security and API boundaries for the identity foundation
before database models or public routes are introduced.  Nothing here creates
users, sessions, organizations, tokens, or credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RegistrationMode(StrEnum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"
    INVITATION = "invitation"
    ENTERPRISE_APPLICATION = "enterprise_application"
    PLATFORM_ADMIN_BOOTSTRAP = "platform_admin_bootstrap"


class AccountStatus(StrEnum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    LOCKED = "locked"
    DISABLED = "disabled"
    DELETED = "deleted"


class MembershipRole(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    ORGANIZATION_OWNER = "organization_owner"
    ORGANIZATION_ADMIN = "organization_admin"
    OPERATOR = "operator"
    AUDITOR = "auditor"
    VIEWER = "viewer"


class AuthActionPurpose(StrEnum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"
    CHANGE_EMAIL = "change_email"
    ACCEPT_INVITATION = "accept_invitation"


PUBLIC_SELF_SERVICE_MODES = (
    RegistrationMode.INDIVIDUAL,
    RegistrationMode.ORGANIZATION,
)

REVIEW_REQUIRED_MODES = (
    RegistrationMode.ENTERPRISE_APPLICATION,
)

INVITABLE_ORGANIZATION_ROLES = (
    MembershipRole.ORGANIZATION_ADMIN,
    MembershipRole.OPERATOR,
    MembershipRole.AUDITOR,
    MembershipRole.VIEWER,
)


class _StrictContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class IndividualRegistrationRequestContract(_StrictContractModel):
    email: str = Field(min_length=3, max_length=320)
    full_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=1024)
    accepted_terms_version: str = Field(min_length=1, max_length=64)


class OrganizationRegistrationRequestContract(
    IndividualRegistrationRequestContract
):
    organization_name: str = Field(min_length=2, max_length=200)


class LoginRequestContract(_StrictContractModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class RegistrationAcceptedResponseContract(_StrictContractModel):
    status: str = "accepted"
    next_action: str = "check_email"


@dataclass(frozen=True, slots=True)
class IdentityRegistrationSecurityContract:
    contract_id: str = "identity_registration_r1"
    public_self_service_modes: tuple[RegistrationMode, ...] = (
        PUBLIC_SELF_SERVICE_MODES
    )
    review_required_modes: tuple[RegistrationMode, ...] = (
        REVIEW_REQUIRED_MODES
    )
    invitable_roles: tuple[MembershipRole, ...] = (
        INVITABLE_ORGANIZATION_ROLES
    )
    password_hash_algorithm: str = "argon2id"
    access_token_storage: str = "memory"
    refresh_token_storage: str = "http_only_cookie"
    session_source_of_truth: str = "postgresql"
    rate_limit_store: str = "redis"
    email_verification_required: bool = True
    refresh_token_rotation_required: bool = True
    refresh_token_reuse_detection_required: bool = True
    csrf_protection_required: bool = True
    tenant_context_server_derived: bool = True
    role_context_server_derived: bool = True
    platform_admin_public_registration: bool = False
    client_selected_role_allowed: bool = False
    client_selected_plan_allowed: bool = False
    raw_password_persisted: bool = False
    raw_action_token_persisted: bool = False
    raw_refresh_token_persisted: bool = False
    redis_is_session_authority: bool = False

    def __post_init__(self) -> None:
        if not self.contract_id.strip():
            raise ValueError("contract_id must not be empty.")
        if self.password_hash_algorithm != "argon2id":
            raise ValueError("User passwords must use Argon2id.")
        if self.access_token_storage != "memory":
            raise ValueError("Browser access tokens must remain memory-only.")
        if self.refresh_token_storage != "http_only_cookie":
            raise ValueError("Refresh tokens must use an HttpOnly cookie.")
        if self.session_source_of_truth != "postgresql":
            raise ValueError("PostgreSQL must remain the session authority.")
        if self.rate_limit_store != "redis":
            raise ValueError("Redis is required only for rate-limit state.")

        required_true = {
            "email_verification_required": self.email_verification_required,
            "refresh_token_rotation_required": (
                self.refresh_token_rotation_required
            ),
            "refresh_token_reuse_detection_required": (
                self.refresh_token_reuse_detection_required
            ),
            "csrf_protection_required": self.csrf_protection_required,
            "tenant_context_server_derived": (
                self.tenant_context_server_derived
            ),
            "role_context_server_derived": self.role_context_server_derived,
        }
        for field_name, enabled in required_true.items():
            if enabled is not True:
                raise ValueError(f"{field_name} must remain enabled.")

        required_false = {
            "platform_admin_public_registration": (
                self.platform_admin_public_registration
            ),
            "client_selected_role_allowed": (
                self.client_selected_role_allowed
            ),
            "client_selected_plan_allowed": (
                self.client_selected_plan_allowed
            ),
            "raw_password_persisted": self.raw_password_persisted,
            "raw_action_token_persisted": (
                self.raw_action_token_persisted
            ),
            "raw_refresh_token_persisted": (
                self.raw_refresh_token_persisted
            ),
            "redis_is_session_authority": self.redis_is_session_authority,
        }
        for field_name, enabled in required_false.items():
            if enabled is not False:
                raise ValueError(f"{field_name} must remain disabled.")

        if RegistrationMode.PLATFORM_ADMIN_BOOTSTRAP in (
            self.public_self_service_modes
        ):
            raise ValueError(
                "Platform-admin bootstrap cannot be public self-service."
            )
        if MembershipRole.PLATFORM_ADMIN in self.invitable_roles:
            raise ValueError("Platform admin cannot be granted by invitation.")
        if MembershipRole.ORGANIZATION_OWNER in self.invitable_roles:
            raise ValueError(
                "Organization ownership requires an explicit transfer flow."
            )


IDENTITY_REGISTRATION_SECURITY_CONTRACT = (
    IdentityRegistrationSecurityContract()
)


def get_identity_registration_security_contract(
) -> IdentityRegistrationSecurityContract:
    return IDENTITY_REGISTRATION_SECURITY_CONTRACT


__all__ = [
    "AccountStatus",
    "AuthActionPurpose",
    "IDENTITY_REGISTRATION_SECURITY_CONTRACT",
    "INVITABLE_ORGANIZATION_ROLES",
    "IdentityRegistrationSecurityContract",
    "IndividualRegistrationRequestContract",
    "LoginRequestContract",
    "MembershipRole",
    "OrganizationRegistrationRequestContract",
    "PUBLIC_SELF_SERVICE_MODES",
    "REVIEW_REQUIRED_MODES",
    "RegistrationAcceptedResponseContract",
    "RegistrationMode",
    "get_identity_registration_security_contract",
]
