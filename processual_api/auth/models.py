from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from processual_api.db.base import Base


def _uuid_column() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _updated_at_column() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class IdentityUser(Base):
    __tablename__ = "identity_users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_verification', 'active', 'locked', 'disabled', 'deleted')",
            name="status_allowed",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_verification")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = _updated_at_column()

    memberships: Mapped[list[OrganizationMembership]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="OrganizationMembership.user_id",
    )
    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    mfa_factors: Mapped[list[AuthMfaFactor]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    terms_acceptances: Mapped[list[IdentityTermsAcceptance]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class IdentityOrganization(Base):
    __tablename__ = "identity_organizations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_review', 'active', 'suspended', 'closed')",
            name="status_allowed",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    slug_normalized: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_review")
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = _updated_at_column()

    memberships: Mapped[list[OrganizationMembership]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class IdentityTermsAcceptance(Base):
    __tablename__ = "identity_terms_acceptances"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "terms_version",
            name="uq_identity_terms_acceptance_user_version",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    terms_version: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[IdentityUser] = relationship(back_populates="terms_acceptances")


class OrganizationMembership(Base):
    __tablename__ = "identity_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_identity_membership_user_org"),
        CheckConstraint(
            "role IN ('organization_owner', 'organization_admin', 'operator', 'auditor', 'viewer')",
            name="role_allowed",
        ),
        CheckConstraint(
            "status IN ('invited', 'active', 'suspended', 'revoked')",
            name="status_allowed",
        ),
        Index("ix_identity_memberships_organization_role", "organization_id", "role"),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="invited")
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="SET NULL"),
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = _updated_at_column()

    user: Mapped[IdentityUser] = relationship(
        back_populates="memberships",
        foreign_keys=[user_id],
    )
    organization: Mapped[IdentityOrganization] = relationship(back_populates="memberships")


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user_active", "user_id", "revoked_at", "expires_at"),)

    id: Mapped[uuid.UUID] = _uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_organizations.id", ondelete="SET NULL"),
    )
    refresh_family_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mfa_satisfied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = _created_at_column()

    user: Mapped[IdentityUser] = relationship(back_populates="sessions")
    refresh_tokens: Mapped[list[AuthRefreshToken]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"
    __table_args__ = (Index("ix_auth_refresh_tokens_session_expiry", "session_id", "expires_at"),)

    id: Mapped[uuid.UUID] = _uuid_column()
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auth_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_token_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auth_refresh_tokens.id", ondelete="SET NULL"),
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reuse_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped[AuthSession] = relationship(back_populates="refresh_tokens")


class AuthActionToken(Base):
    __tablename__ = "auth_action_tokens"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('verify_email', 'reset_password', 'change_email', 'accept_invitation')",
            name="purpose_allowed",
        ),
        Index("ix_auth_action_tokens_user_purpose", "user_id", "purpose", "expires_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at_column()

    user: Mapped[IdentityUser] = relationship()


class AuthDeliveryOutbox(Base):
    __tablename__ = "auth_delivery_outbox"
    __table_args__ = (
        CheckConstraint("event_type IN ('verify_email')", name="event_type_allowed"),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        Index("ix_auth_delivery_outbox_pending", "delivered_at", "available_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_token_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auth_action_tokens.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload_key_version: Mapped[str] = mapped_column(String(40), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = _created_at_column()

    user: Mapped[IdentityUser] = relationship()
    action_token: Mapped[AuthActionToken] = relationship()


class AuthMfaFactor(Base):
    __tablename__ = "auth_mfa_factors"
    __table_args__ = (
        CheckConstraint("factor_type IN ('totp')", name="factor_type_allowed"),
        CheckConstraint("status IN ('pending', 'active', 'disabled')", name="status_allowed"),
        UniqueConstraint("user_id", "factor_type", "label", name="uq_auth_mfa_factor_user_type_label"),
        Index("ix_auth_mfa_factors_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    factor_type: Mapped[str] = mapped_column(String(24), nullable=False, default="totp")
    label: Mapped[str] = mapped_column(String(80), nullable=False, default="Authenticator")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    secret_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    secret_key_version: Mapped[str] = mapped_column(String(40), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_step: Mapped[int | None] = mapped_column(BigInteger)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = _updated_at_column()

    user: Mapped[IdentityUser] = relationship(back_populates="mfa_factors")
    recovery_codes: Mapped[list[AuthMfaRecoveryCode]] = relationship(
        back_populates="factor",
        cascade="all, delete-orphan",
    )


class AuthMfaRecoveryCode(Base):
    __tablename__ = "auth_mfa_recovery_codes"

    id: Mapped[uuid.UUID] = _uuid_column()
    factor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auth_mfa_factors.id", ondelete="CASCADE"),
        nullable=False,
    )
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at_column()

    factor: Mapped[AuthMfaFactor] = relationship(back_populates="recovery_codes")


class AuthMfaChallenge(Base):
    __tablename__ = "auth_mfa_challenges"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'verified', 'expired', 'locked')", name="status_allowed"),
        Index("ix_auth_mfa_challenges_user_expiry", "user_id", "expires_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    challenge_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at_column()


IDENTITY_AUTH_MODELS = (
    IdentityUser,
    IdentityOrganization,
    IdentityTermsAcceptance,
    OrganizationMembership,
    AuthSession,
    AuthRefreshToken,
    AuthActionToken,
    AuthMfaFactor,
    AuthMfaRecoveryCode,
    AuthMfaChallenge,
)


__all__ = [
    *[model.__name__ for model in IDENTITY_AUTH_MODELS],
    "AuthDeliveryOutbox",
]
