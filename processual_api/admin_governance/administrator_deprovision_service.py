from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class AdministratorDeprovisionRepository(Protocol):
    async def active_platform_admin_for_update(self, *, user_id: uuid.UUID): ...

    async def platform_supervisor_for_update(self, *, user_id: uuid.UUID): ...

    async def active_permission_grants_for_update(self, *, user_id: uuid.UUID): ...

    async def revoke_all_sessions(
        self,
        *,
        user_id: uuid.UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None: ...

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
    ): ...


class AdministratorDeprovisionUnitOfWork(Protocol):
    repository: AdministratorDeprovisionRepository

    async def __aenter__(self): ...

    async def __aexit__(self, exc_type, exc, traceback): ...

    async def commit(self) -> None: ...


class AdministratorDeprovisionDeniedError(RuntimeError):
    pass


class AdministratorDeprovisionConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdministratorDeprovisionReceipt:
    user_id: uuid.UUID
    status: str
    revoked_permission_count: int
    occurred_at: datetime


class AdministratorDeprovisionService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdministratorDeprovisionUnitOfWork],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Administrator deprovision clock must be timezone-aware.")
        return now

    @staticmethod
    def _normalize_reason(value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 12 or len(normalized) > 500:
            raise ValueError("Administrator deprovision reason is invalid.")
        return normalized

    async def revoke_supervisor_authority(
        self,
        *,
        actor_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        reason: str,
        recent_step_up: bool,
    ) -> AdministratorDeprovisionReceipt:
        if not recent_step_up:
            raise AdministratorDeprovisionDeniedError("recent_mfa_step_up_required")
        normalized_reason = self._normalize_reason(reason)
        now = self._now()

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            actor_admin = await repository.active_platform_admin_for_update(
                user_id=actor_user_id
            )
            if actor_admin is None:
                raise AdministratorDeprovisionDeniedError(
                    "active_platform_administrator_required"
                )

            target_admin = await repository.active_platform_admin_for_update(
                user_id=target_user_id
            )
            if target_admin is not None:
                raise AdministratorDeprovisionDeniedError(
                    "platform_administrator_deprovision_denied"
                )

            authority = await repository.platform_supervisor_for_update(
                user_id=target_user_id
            )
            if authority is None or authority.status != "active":
                raise AdministratorDeprovisionConflictError(
                    "Administrator supervisor authority is not active."
                )

            permission_grants = tuple(
                await repository.active_permission_grants_for_update(
                    user_id=target_user_id
                )
            )
            for grant in permission_grants:
                grant.status = "revoked"
                grant.revoked_by_user_id = actor_user_id
                grant.revocation_reason = normalized_reason
                grant.revoked_at = now
                repository.add_governance_audit_event(
                    event_type="administrator.permission.revoked",
                    actor_user_id=actor_user_id,
                    subject_user_id=target_user_id,
                    invitation_id=grant.source_invitation_id,
                    permission=grant.permission,
                    reason=normalized_reason,
                    occurred_at=now,
                )

            authority.status = "revoked"
            authority.revoked_by_user_id = actor_user_id
            authority.revoke_reason = normalized_reason
            authority.revoked_at = now
            await repository.revoke_all_sessions(
                user_id=target_user_id,
                revoked_at=now,
                reason="administrator_supervisor_authority_revoked",
            )
            repository.add_governance_audit_event(
                event_type="administrator.supervisor_authority.revoked",
                actor_user_id=actor_user_id,
                subject_user_id=target_user_id,
                invitation_id=None,
                permission=None,
                reason=normalized_reason,
                occurred_at=now,
            )
            await unit.commit()

        return AdministratorDeprovisionReceipt(
            user_id=target_user_id,
            status="revoked",
            revoked_permission_count=len(permission_grants),
            occurred_at=now,
        )


__all__ = [
    "AdministratorDeprovisionConflictError",
    "AdministratorDeprovisionDeniedError",
    "AdministratorDeprovisionReceipt",
    "AdministratorDeprovisionService",
]
