from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from processual_api.auth.normalization import normalize_email


class RecoveryEmailRepository(Protocol):
    async def platform_admin_user(self, *, user_id: uuid.UUID): ...
    async def email_owner(self, *, email_normalized: str): ...
    async def recovery_email_for_update(self, *, user_id: uuid.UUID): ...
    def add_recovery_email(
        self,
        *,
        user_id: uuid.UUID,
        email_normalized: str,
        now: datetime,
    ): ...


class RecoveryEmailUnitOfWork(Protocol):
    repository: RecoveryEmailRepository
    async def __aenter__(self): ...
    async def __aexit__(self, exc_type, exc, traceback): ...
    async def commit(self) -> None: ...


class RecoveryEmailDeniedError(RuntimeError):
    pass


class RecoveryEmailConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RecoveryEmailReceipt:
    user_id: uuid.UUID
    email_normalized: str
    status: str


class AdminRecoveryEmailService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], RecoveryEmailUnitOfWork],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Recovery-email clock must be timezone-aware.")
        return now

    async def set_pending(
        self,
        *,
        actor_user_id: uuid.UUID,
        recovery_email: str,
        recent_step_up: bool,
    ) -> RecoveryEmailReceipt:
        if not recent_step_up:
            raise RecoveryEmailDeniedError("Recent MFA step-up is required.")

        email_normalized = normalize_email(recovery_email)
        now = self._now()

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            actor = await repository.platform_admin_user(user_id=actor_user_id)
            if actor is None:
                raise RecoveryEmailDeniedError(
                    "Active platform administrator authority is required."
                )
            if actor.email_normalized == email_normalized:
                raise RecoveryEmailConflictError(
                    "Recovery email must differ from the primary email."
                )

            owner = await repository.email_owner(
                email_normalized=email_normalized
            )
            if owner is not None and owner != actor_user_id:
                raise RecoveryEmailConflictError(
                    "Recovery email is already owned by another identity."
                )

            current = await repository.recovery_email_for_update(
                user_id=actor_user_id
            )
            if current is None:
                current = repository.add_recovery_email(
                    user_id=actor_user_id,
                    email_normalized=email_normalized,
                    now=now,
                )
            else:
                current.email_normalized = email_normalized
                current.status = "pending"
                current.verified_at = None
                current.revoked_at = None
                current.updated_at = now

            await unit.commit()
            return RecoveryEmailReceipt(
                user_id=actor_user_id,
                email_normalized=email_normalized,
                status="pending",
            )

    async def mark_verified(
        self,
        *,
        actor_user_id: uuid.UUID,
        expected_email: str,
    ) -> RecoveryEmailReceipt:
        now = self._now()
        email_normalized = normalize_email(expected_email)

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            actor = await repository.platform_admin_user(user_id=actor_user_id)
            if actor is None:
                raise RecoveryEmailDeniedError(
                    "Active platform administrator authority is required."
                )

            current = await repository.recovery_email_for_update(
                user_id=actor_user_id
            )
            if (
                current is None
                or current.status != "pending"
                or current.email_normalized != email_normalized
            ):
                raise RecoveryEmailDeniedError(
                    "Pending recovery email verification is unavailable."
                )

            current.status = "verified"
            current.verified_at = now
            current.revoked_at = None
            current.updated_at = now
            await unit.commit()

            return RecoveryEmailReceipt(
                user_id=actor_user_id,
                email_normalized=email_normalized,
                status="verified",
            )

    async def revoke(
        self,
        *,
        actor_user_id: uuid.UUID,
        recent_step_up: bool,
    ) -> RecoveryEmailReceipt:
        if not recent_step_up:
            raise RecoveryEmailDeniedError("Recent MFA step-up is required.")

        now = self._now()
        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            actor = await repository.platform_admin_user(user_id=actor_user_id)
            if actor is None:
                raise RecoveryEmailDeniedError(
                    "Active platform administrator authority is required."
                )

            current = await repository.recovery_email_for_update(
                user_id=actor_user_id
            )
            if current is None or current.status == "revoked":
                raise RecoveryEmailDeniedError(
                    "Active recovery email is unavailable."
                )

            current.status = "revoked"
            current.revoked_at = now
            current.updated_at = now
            await unit.commit()
            return RecoveryEmailReceipt(
                user_id=actor_user_id,
                email_normalized=current.email_normalized,
                status="revoked",
            )
