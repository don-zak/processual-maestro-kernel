from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_governance.models import (
    AdministratorGovernanceAuditEvent,
    AdministratorInvitation,
    AdministratorPermissionGrant,
)
from processual_api.auth.models import (
    AuthMfaFactor,
    AuthMfaRecoveryCode,
    AuthRefreshToken,
    AuthSession,
    IdentityPlatformAuthority,
    IdentityUser,
)


class SqlAlchemyAdministratorInvitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def active_platform_admin(self, *, user_id: uuid.UUID):
        return await self._session.scalar(
            select(IdentityPlatformAuthority)
            .join(IdentityUser, IdentityUser.id == IdentityPlatformAuthority.user_id)
            .where(
                IdentityPlatformAuthority.user_id == user_id,
                IdentityPlatformAuthority.authority == "platform_admin",
                IdentityPlatformAuthority.status == "active",
                IdentityUser.status == "active",
            )
        )

    async def identity_exists(self, *, email_normalized: str) -> bool:
        user_id = await self._session.scalar(
            select(IdentityUser.id)
            .where(IdentityUser.email_normalized == email_normalized)
            .limit(1)
        )
        return user_id is not None

    async def active_invitation_for_email(self, *, email_normalized: str):
        now = datetime.now(UTC)
        return await self._session.scalar(
            select(AdministratorInvitation)
            .where(
                AdministratorInvitation.email_normalized == email_normalized,
                AdministratorInvitation.status == "pending",
                AdministratorInvitation.expires_at > now,
            )
            .order_by(AdministratorInvitation.created_at.desc())
            .limit(1)
        )

    async def invitation_by_id(self, *, invitation_id: uuid.UUID):
        return await self._session.scalar(
            select(AdministratorInvitation)
            .where(AdministratorInvitation.id == invitation_id)
            .limit(1)
        )

    async def invitation_for_update(self, *, invitation_id: uuid.UUID):
        return await self._session.scalar(
            select(AdministratorInvitation)
            .where(AdministratorInvitation.id == invitation_id)
            .with_for_update()
        )

    async def onboarding_user_for_update(self, *, user_id: uuid.UUID):
        return await self._session.scalar(
            select(IdentityUser).where(IdentityUser.id == user_id).with_for_update()
        )

    async def administrator_for_update(self, *, user_id: uuid.UUID):
        return await self._session.scalar(
            select(IdentityUser).where(IdentityUser.id == user_id).with_for_update()
        )

    async def platform_supervisor_for_update(self, *, user_id: uuid.UUID):
        return await self._session.scalar(
            select(IdentityPlatformAuthority)
            .where(
                IdentityPlatformAuthority.user_id == user_id,
                IdentityPlatformAuthority.authority == "platform_supervisor",
            )
            .with_for_update()
        )

    async def revoke_all_sessions(
        self,
        *,
        user_id: uuid.UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        session_ids = select(AuthSession.id).where(AuthSession.user_id == user_id)
        await self._session.execute(
            update(AuthRefreshToken)
            .where(
                AuthRefreshToken.session_id.in_(session_ids),
                AuthRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        await self._session.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at, revoke_reason=reason)
        )

    async def platform_authority_for_update(
        self,
        *,
        user_id: uuid.UUID,
        authority: str,
    ):
        return await self._session.scalar(
            select(IdentityPlatformAuthority)
            .where(
                IdentityPlatformAuthority.user_id == user_id,
                IdentityPlatformAuthority.authority == authority,
            )
            .with_for_update()
        )

    async def permission_grant_for_update(
        self,
        *,
        user_id: uuid.UUID,
        permission: str,
    ):
        return await self._session.scalar(
            select(AdministratorPermissionGrant)
            .where(
                AdministratorPermissionGrant.user_id == user_id,
                AdministratorPermissionGrant.permission == permission,
            )
            .with_for_update()
        )

    async def active_mfa_factor_for_update(self, *, user_id: uuid.UUID):
        return await self._session.scalar(
            select(AuthMfaFactor)
            .where(AuthMfaFactor.user_id == user_id, AuthMfaFactor.status == "active")
            .order_by(AuthMfaFactor.created_at.desc())
            .limit(1)
            .with_for_update()
        )

    async def pending_mfa_factor_for_update(self, *, user_id: uuid.UUID):
        return await self._session.scalar(
            select(AuthMfaFactor)
            .where(AuthMfaFactor.user_id == user_id, AuthMfaFactor.status == "pending")
            .order_by(AuthMfaFactor.created_at.desc())
            .limit(1)
            .with_for_update()
        )

    async def disable_pending_mfa_factors(
        self,
        *,
        user_id: uuid.UUID,
        disabled_at: datetime,
    ) -> None:
        await self._session.execute(
            update(AuthMfaFactor)
            .where(AuthMfaFactor.user_id == user_id, AuthMfaFactor.status == "pending")
            .values(status="disabled", disabled_at=disabled_at)
        )

    def add_pending_mfa_factor(
        self,
        *,
        factor_id: uuid.UUID,
        user_id: uuid.UUID,
        label: str,
        ciphertext: bytes,
        key_version: str,
    ) -> None:
        self._session.add(
            AuthMfaFactor(
                id=factor_id,
                user_id=user_id,
                factor_type="totp",
                label=label,
                status="pending",
                secret_ciphertext=ciphertext,
                secret_key_version=key_version,
            )
        )

    async def replace_mfa_recovery_codes(
        self,
        *,
        factor_id: uuid.UUID,
        code_hashes: tuple[str, ...],
    ) -> None:
        await self._session.execute(
            delete(AuthMfaRecoveryCode).where(AuthMfaRecoveryCode.factor_id == factor_id)
        )
        self._session.add_all(
            AuthMfaRecoveryCode(factor_id=factor_id, code_hash=code_hash)
            for code_hash in code_hashes
        )

    def add_onboarding_identity(
        self,
        *,
        user_id: uuid.UUID,
        email_normalized: str,
        display_name: str,
        password_hash: str,
        verified_at: datetime,
    ) -> IdentityUser:
        user = IdentityUser(
            id=user_id,
            email_normalized=email_normalized,
            display_name=display_name,
            password_hash=password_hash,
            status="pending_verification",
            email_verified_at=verified_at,
            password_changed_at=verified_at,
        )
        self._session.add(user)
        return user

    def add_platform_supervisor_authority(
        self,
        *,
        user_id: uuid.UUID,
        granted_by_user_id: uuid.UUID,
        reason: str,
        granted_at: datetime,
    ) -> IdentityPlatformAuthority:
        row = IdentityPlatformAuthority(
            user_id=user_id,
            authority="platform_supervisor",
            status="active",
            granted_by_user_id=granted_by_user_id,
            grant_reason=reason,
            granted_at=granted_at,
        )
        self._session.add(row)
        return row

    def add_permission_grant(
        self,
        *,
        user_id: uuid.UUID,
        permission: str,
        invitation_id: uuid.UUID,
        granted_by_user_id: uuid.UUID,
        reason: str,
        granted_at: datetime,
    ) -> AdministratorPermissionGrant:
        row = AdministratorPermissionGrant(
            user_id=user_id,
            permission=permission,
            status="active",
            source_invitation_id=invitation_id,
            granted_by_user_id=granted_by_user_id,
            grant_reason=reason,
            granted_at=granted_at,
        )
        self._session.add(row)
        return row

    def add_governance_audit_event(
        self,
        *,
        event_type: str,
        actor_user_id: uuid.UUID | None,
        subject_user_id: uuid.UUID,
        invitation_id: uuid.UUID | None,
        permission: str | None,
        reason: str,
        occurred_at: datetime,
    ) -> AdministratorGovernanceAuditEvent:
        row = AdministratorGovernanceAuditEvent(
            event_type=event_type,
            actor_user_id=actor_user_id,
            subject_user_id=subject_user_id,
            invitation_id=invitation_id,
            permission=permission,
            reason=reason,
            occurred_at=occurred_at,
        )
        self._session.add(row)
        return row

    @staticmethod
    def bind_invitation_to_onboarding_identity(
        invitation: AdministratorInvitation,
        *,
        user_id: uuid.UUID,
        bound_at: datetime,
        mfa_proof_hash: str,
        mfa_proof_expires_at: datetime,
    ) -> None:
        invitation.accepted_by_user_id = user_id
        invitation.accepted_at = bound_at
        invitation.onboarding_mfa_proof_hash = mfa_proof_hash
        invitation.onboarding_mfa_proof_expires_at = mfa_proof_expires_at
        invitation.updated_at = bound_at

    @staticmethod
    def complete_mfa_onboarding(
        invitation: AdministratorInvitation,
        *,
        completed_at: datetime,
    ) -> None:
        invitation.status = "accepted"
        invitation.onboarding_mfa_proof_hash = None
        invitation.onboarding_mfa_proof_expires_at = None
        invitation.updated_at = completed_at

    def add_invitation(self, **values) -> AdministratorInvitation:
        row = AdministratorInvitation(
            id=values["invitation_id"],
            email_normalized=values["email_normalized"],
            supervision_level=values["supervision_level"],
            token_hash=values["token_hash"],
            status=values["status"],
            invited_by_user_id=values["invited_by_user_id"],
            invite_reason=values["invite_reason"],
            expires_at=values["expires_at"],
            created_at=values["created_at"],
            updated_at=values["created_at"],
        )
        self._session.add(row)
        return row


class SqlAlchemyAdministratorInvitationUnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.repository: SqlAlchemyAdministratorInvitationRepository | None = None
        self._committed = False

    async def __aenter__(self):
        self._session = self._session_factory()
        self.repository = SqlAlchemyAdministratorInvitationRepository(self._session)
        return self

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Administrator invitation unit of work is not active.")
        await self._session.commit()
        self._committed = True

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._session is None:
            return
        if exc is not None or not self._committed:
            await self._session.rollback()
        await self._session.close()


__all__ = [
    "SqlAlchemyAdministratorInvitationRepository",
    "SqlAlchemyAdministratorInvitationUnitOfWork",
]
