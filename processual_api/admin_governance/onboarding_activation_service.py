# ruff: noqa: I001
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID


REVIEW_SUPERVISOR_PERMISSIONS = frozenset(
    {
        "governance.administrators.view",
        "governance.activity.view",
    }
)
OPERATIONS_SUPERVISOR_PERMISSIONS = frozenset(
    {
        *REVIEW_SUPERVISOR_PERMISSIONS,
        "governance.sessions.view",
        "governance.session.revoke",
        "governance.administrator.freeze",
        "governance.administrator.restore",
    }
)
PERMISSIONS_BY_SUPERVISION_LEVEL = {
    "review_supervisor": REVIEW_SUPERVISOR_PERMISSIONS,
    "operations_supervisor": OPERATIONS_SUPERVISOR_PERMISSIONS,
}


class AdministratorOnboardingActivationRepository(Protocol):
    async def invitation_for_update(self, *, invitation_id: UUID): ...
    async def onboarding_user_for_update(self, *, user_id: UUID): ...
    async def active_mfa_factor_for_update(self, *, user_id: UUID): ...
    async def active_platform_admin(self, *, user_id: UUID): ...
    async def platform_authority_for_update(
        self,
        *,
        user_id: UUID,
        authority: str,
    ): ...
    async def permission_grant_for_update(
        self,
        *,
        user_id: UUID,
        permission: str,
    ): ...
    def add_platform_supervisor_authority(self, **values): ...
    def add_permission_grant(self, **values): ...
    def add_governance_audit_event(self, **values): ...


class AdministratorOnboardingActivationUnitOfWork(Protocol):
    repository: AdministratorOnboardingActivationRepository
    async def __aenter__(self): ...
    async def __aexit__(self, exc_type, exc, traceback): ...
    async def commit(self) -> None: ...


class AdministratorOnboardingActivationDeniedError(RuntimeError):
    pass


class AdministratorOnboardingActivationConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdministratorOnboardingActivationReceipt:
    invitation_id: UUID
    user_id: UUID
    supervision_level: str
    platform_authority: str
    permissions: tuple[str, ...]
    status: str = "active"


class AdministratorOnboardingActivationService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdministratorOnboardingActivationUnitOfWork],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Administrator activation clock must be timezone-aware.")
        return now

    @staticmethod
    def _permissions(supervision_level: str) -> tuple[str, ...]:
        permissions = PERMISSIONS_BY_SUPERVISION_LEVEL.get(supervision_level)
        if permissions is None:
            raise AdministratorOnboardingActivationDeniedError(
                "Administrator supervision level is not activatable."
            )
        ordered = tuple(sorted(permissions))
        if any("*" in permission for permission in ordered):
            raise AdministratorOnboardingActivationDeniedError(
                "Wildcard administrator permissions are prohibited."
            )
        return ordered

    async def activate(
        self,
        *,
        invitation_id: UUID,
        user_id: UUID,
    ) -> AdministratorOnboardingActivationReceipt:
        now = self._now()
        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            invitation = await repository.invitation_for_update(invitation_id=invitation_id)
            if (
                invitation is None
                or invitation.status != "accepted"
                or invitation.accepted_by_user_id != user_id
                or invitation.onboarding_mfa_proof_hash is not None
                or invitation.onboarding_mfa_proof_expires_at is not None
            ):
                raise AdministratorOnboardingActivationDeniedError(
                    "Completed administrator invitation is required for activation."
                )

            user = await repository.onboarding_user_for_update(user_id=user_id)
            if (
                user is None
                or user.status != "pending_verification"
                or user.email_verified_at is None
                or user.email_normalized != invitation.email_normalized
            ):
                raise AdministratorOnboardingActivationDeniedError(
                    "Pending verified onboarding identity is required for activation."
                )
            if await repository.active_mfa_factor_for_update(user_id=user_id) is None:
                raise AdministratorOnboardingActivationDeniedError(
                    "Active administrator MFA is required for activation."
                )
            actor_user_id = invitation.invited_by_user_id
            if await repository.active_platform_admin(user_id=actor_user_id) is None:
                raise AdministratorOnboardingActivationDeniedError(
                    "The inviting platform administrator must remain active."
                )

            permissions = self._permissions(invitation.supervision_level)
            existing_authority = await repository.platform_authority_for_update(
                user_id=user_id,
                authority="platform_supervisor",
            )
            if existing_authority is not None:
                raise AdministratorOnboardingActivationConflictError(
                    "Administrator platform authority already exists."
                )
            for permission in permissions:
                existing = await repository.permission_grant_for_update(
                    user_id=user_id,
                    permission=permission,
                )
                if existing is not None:
                    raise AdministratorOnboardingActivationConflictError(
                        "Administrator permission grant already exists."
                    )

            reason = invitation.invite_reason
            repository.add_platform_supervisor_authority(
                user_id=user_id,
                granted_by_user_id=actor_user_id,
                reason=reason,
                granted_at=now,
            )
            for permission in permissions:
                repository.add_permission_grant(
                    user_id=user_id,
                    permission=permission,
                    invitation_id=invitation_id,
                    granted_by_user_id=actor_user_id,
                    reason=reason,
                    granted_at=now,
                )
                repository.add_governance_audit_event(
                    event_type="administrator.permission.granted",
                    actor_user_id=actor_user_id,
                    subject_user_id=user_id,
                    invitation_id=invitation_id,
                    permission=permission,
                    reason=reason,
                    occurred_at=now,
                )

            user.status = "active"
            user.updated_at = now
            repository.add_governance_audit_event(
                event_type="administrator.activated",
                actor_user_id=actor_user_id,
                subject_user_id=user_id,
                invitation_id=invitation_id,
                permission=None,
                reason=reason,
                occurred_at=now,
            )
            await unit.commit()

        return AdministratorOnboardingActivationReceipt(
            invitation_id=invitation_id,
            user_id=user_id,
            supervision_level=invitation.supervision_level,
            platform_authority="platform_supervisor",
            permissions=permissions,
        )


__all__ = [
    "AdministratorOnboardingActivationConflictError",
    "AdministratorOnboardingActivationDeniedError",
    "AdministratorOnboardingActivationReceipt",
    "AdministratorOnboardingActivationService",
    "OPERATIONS_SUPERVISOR_PERMISSIONS",
    "PERMISSIONS_BY_SUPERVISION_LEVEL",
    "REVIEW_SUPERVISOR_PERMISSIONS",
]
