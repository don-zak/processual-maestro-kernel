from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class AdministratorInvitationLifecycleRepository(Protocol):
    async def active_platform_admin(self, *, user_id: uuid.UUID): ...
    async def invitation_for_update(self, *, invitation_id: uuid.UUID): ...
    def add_governance_audit_event(self, **values): ...


class AdministratorInvitationLifecycleUnitOfWork(Protocol):
    repository: AdministratorInvitationLifecycleRepository

    async def __aenter__(self): ...
    async def __aexit__(self, exc_type, exc, traceback): ...
    async def commit(self) -> None: ...


class AdministratorInvitationLifecycleDeniedError(RuntimeError):
    pass


class AdministratorInvitationLifecycleConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdministratorInvitationCancellationReceipt:
    invitation_id: uuid.UUID
    cancelled_by_user_id: uuid.UUID
    cancelled_at: datetime
    status: str = "cancelled"


class AdministratorInvitationLifecycleService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdministratorInvitationLifecycleUnitOfWork],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Administrator invitation lifecycle clock must be timezone-aware.")
        return now

    @staticmethod
    def _normalize_reason(value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 12 or len(normalized) > 500:
            raise ValueError("Administrator invitation cancellation reason is invalid.")
        return normalized

    async def cancel(
        self,
        *,
        invitation_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        reason: str,
        recent_step_up: bool,
    ) -> AdministratorInvitationCancellationReceipt:
        if not recent_step_up:
            raise AdministratorInvitationLifecycleDeniedError(
                "Recent platform-administrator MFA step-up is required."
            )

        normalized_reason = self._normalize_reason(reason)
        now = self._now()

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            if await repository.active_platform_admin(user_id=actor_user_id) is None:
                raise AdministratorInvitationLifecycleDeniedError(
                    "Active platform administrator authority is required."
                )

            invitation = await repository.invitation_for_update(
                invitation_id=invitation_id
            )
            if invitation is None:
                raise AdministratorInvitationLifecycleConflictError(
                    "Administrator invitation is not cancellable."
                )

            expires_at = invitation.expires_at
            if expires_at.tzinfo is None:
                raise AdministratorInvitationLifecycleDeniedError(
                    "Administrator invitation expiry must be timezone-aware."
                )
            if (
                invitation.status != "pending"
                or invitation.accepted_by_user_id is not None
                or expires_at <= now
            ):
                raise AdministratorInvitationLifecycleConflictError(
                    "Administrator invitation is not cancellable."
                )

            invitation.status = "cancelled"
            invitation.cancelled_by_user_id = actor_user_id
            invitation.cancelled_at = now
            invitation.cancellation_reason = normalized_reason
            invitation.updated_at = now
            repository.add_governance_audit_event(
                event_type="administrator_invitation_cancelled",
                actor_user_id=actor_user_id,
                subject_user_id=None,
                invitation_id=invitation_id,
                permission=None,
                reason=normalized_reason,
                occurred_at=now,
            )
            await unit.commit()

        return AdministratorInvitationCancellationReceipt(
            invitation_id=invitation_id,
            cancelled_by_user_id=actor_user_id,
            cancelled_at=now,
        )


__all__ = [
    "AdministratorInvitationCancellationReceipt",
    "AdministratorInvitationLifecycleConflictError",
    "AdministratorInvitationLifecycleDeniedError",
    "AdministratorInvitationLifecycleService",
]
