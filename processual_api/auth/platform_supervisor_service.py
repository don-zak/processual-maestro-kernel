from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class SupervisorRepository(Protocol):
    async def active_platform_admin(self, *, user_id: uuid.UUID): ...
    async def active_user(self, *, user_id: uuid.UUID): ...
    async def authority_for_update(
        self,
        *,
        user_id: uuid.UUID,
        authority: str,
    ): ...
    def add_supervisor_authority(
        self,
        *,
        user_id: uuid.UUID,
        granted_by_user_id: uuid.UUID,
        grant_reason: str,
        now: datetime,
    ): ...


class SupervisorUnitOfWork(Protocol):
    repository: SupervisorRepository
    async def __aenter__(self): ...
    async def __aexit__(self, exc_type, exc, traceback): ...
    async def commit(self) -> None: ...


class PlatformSupervisorDeniedError(RuntimeError):
    pass


class PlatformSupervisorConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PlatformSupervisorReceipt:
    user_id: uuid.UUID
    authority: str
    status: str
    actor_user_id: uuid.UUID
    reason: str


class PlatformSupervisorService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], SupervisorUnitOfWork],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Supervisor clock must be timezone-aware.")
        return now

    @staticmethod
    def _reason(value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 12 or len(normalized) > 500:
            raise ValueError("Supervisor authority reason is invalid.")
        return normalized

    async def grant(
        self,
        *,
        actor_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        reason: str,
        recent_step_up: bool,
    ) -> PlatformSupervisorReceipt:
        if not recent_step_up:
            raise PlatformSupervisorDeniedError(
                "Recent platform-administrator MFA step-up is required."
            )
        if actor_user_id == target_user_id:
            raise PlatformSupervisorDeniedError("Self-delegation is not allowed.")

        reason = self._reason(reason)
        now = self._now()
        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            if await repository.active_platform_admin(
                user_id=actor_user_id
            ) is None:
                raise PlatformSupervisorDeniedError(
                    "Active platform administrator authority is required."
                )
            if await repository.active_user(user_id=target_user_id) is None:
                raise PlatformSupervisorDeniedError(
                    "Target identity must be active and email-verified."
                )

            target_admin = await repository.authority_for_update(
                user_id=target_user_id,
                authority="platform_admin",
            )
            if target_admin is not None and target_admin.status == "active":
                raise PlatformSupervisorDeniedError(
                    "Platform administrator cannot be delegated as supervisor."
                )

            authority = await repository.authority_for_update(
                user_id=target_user_id,
                authority="platform_supervisor",
            )
            if authority is None:
                authority = repository.add_supervisor_authority(
                    user_id=target_user_id,
                    granted_by_user_id=actor_user_id,
                    grant_reason=reason,
                    now=now,
                )
            elif authority.status == "active":
                raise PlatformSupervisorConflictError(
                    "Platform supervisor authority is already active."
                )
            else:
                authority.status = "active"
                authority.granted_by_user_id = actor_user_id
                authority.grant_reason = reason
                authority.granted_at = now
                authority.revoked_at = None
                authority.revoked_by_user_id = None
                authority.revocation_reason = None

            await unit.commit()
            return PlatformSupervisorReceipt(
                user_id=target_user_id,
                authority="platform_supervisor",
                status="active",
                actor_user_id=actor_user_id,
                reason=reason,
            )

    async def revoke(
        self,
        *,
        actor_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        reason: str,
        recent_step_up: bool,
    ) -> PlatformSupervisorReceipt:
        if not recent_step_up:
            raise PlatformSupervisorDeniedError(
                "Recent platform-administrator MFA step-up is required."
            )
        if actor_user_id == target_user_id:
            raise PlatformSupervisorDeniedError(
                "Self-revocation through delegation is not allowed."
            )

        reason = self._reason(reason)
        now = self._now()
        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            if await repository.active_platform_admin(
                user_id=actor_user_id
            ) is None:
                raise PlatformSupervisorDeniedError(
                    "Active platform administrator authority is required."
                )

            authority = await repository.authority_for_update(
                user_id=target_user_id,
                authority="platform_supervisor",
            )
            if authority is None or authority.status != "active":
                raise PlatformSupervisorDeniedError(
                    "Active platform supervisor authority is unavailable."
                )

            authority.status = "revoked"
            authority.revoked_at = now
            authority.revoked_by_user_id = actor_user_id
            authority.revocation_reason = reason
            await unit.commit()

            return PlatformSupervisorReceipt(
                user_id=target_user_id,
                authority="platform_supervisor",
                status="revoked",
                actor_user_id=actor_user_id,
                reason=reason,
            )
