from __future__ import annotations

import hashlib
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from processual_api.auth.normalization import normalize_email


class AdministratorInvitationRepository(Protocol):
    async def active_platform_admin(self, *, user_id: uuid.UUID): ...
    async def active_invitation_for_email(self, *, email_normalized: str): ...
    async def identity_exists(self, *, email_normalized: str) -> bool: ...
    def add_invitation(self, **values): ...


class AdministratorInvitationUnitOfWork(Protocol):
    repository: AdministratorInvitationRepository
    async def __aenter__(self): ...
    async def __aexit__(self, exc_type, exc, traceback): ...
    async def commit(self) -> None: ...


class AdministratorInvitationDeniedError(RuntimeError):
    pass


class AdministratorInvitationConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdministratorInvitationCommand:
    email: str
    supervision_level: str
    reason: str
    expires_in_hours: int = 48


@dataclass(frozen=True, slots=True)
class AdministratorInvitationReceipt:
    invitation_id: uuid.UUID
    email_normalized: str
    supervision_level: str
    expires_at: datetime
    invitation_token: str


class AdministratorInvitationService:
    _ALLOWED_LEVELS = frozenset(
        {"operations_supervisor", "review_supervisor"}
    )

    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdministratorInvitationUnitOfWork],
        clock: Callable[[], datetime] | None = None,
        invitation_id_factory: Callable[[], uuid.UUID] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._invitation_id_factory = invitation_id_factory or uuid.uuid4

    @staticmethod
    def _normalize_reason(value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 12 or len(normalized) > 500:
            raise ValueError("Administrator invitation reason is invalid.")
        return normalized

    async def issue(
        self,
        *,
        actor_user_id: uuid.UUID,
        command: AdministratorInvitationCommand,
        recent_step_up: bool,
    ) -> AdministratorInvitationReceipt:
        if not recent_step_up:
            raise AdministratorInvitationDeniedError(
                "Recent platform-administrator MFA step-up is required."
            )

        email_normalized = normalize_email(command.email)
        if command.supervision_level not in self._ALLOWED_LEVELS:
            raise AdministratorInvitationDeniedError(
                "Requested administrator supervision level is not invite-eligible."
            )
        if command.expires_in_hours < 1 or command.expires_in_hours > 168:
            raise ValueError("Administrator invitation expiry is outside its safe range.")

        reason = self._normalize_reason(command.reason)
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Administrator invitation clock must be timezone-aware.")
        expires_at = now + timedelta(hours=command.expires_in_hours)
        invitation_id = self._invitation_id_factory()
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            if await repository.active_platform_admin(user_id=actor_user_id) is None:
                raise AdministratorInvitationDeniedError(
                    "Active platform administrator authority is required."
                )
            if await repository.identity_exists(email_normalized=email_normalized):
                raise AdministratorInvitationConflictError(
                    "An identity already exists for the invited email."
                )
            if await repository.active_invitation_for_email(
                email_normalized=email_normalized
            ) is not None:
                raise AdministratorInvitationConflictError(
                    "An active administrator invitation already exists for this email."
                )

            repository.add_invitation(
                invitation_id=invitation_id,
                email_normalized=email_normalized,
                supervision_level=command.supervision_level,
                token_hash=token_hash,
                status="pending",
                invited_by_user_id=actor_user_id,
                invite_reason=reason,
                expires_at=expires_at,
                created_at=now,
            )
            await unit.commit()

        return AdministratorInvitationReceipt(
            invitation_id=invitation_id,
            email_normalized=email_normalized,
            supervision_level=command.supervision_level,
            expires_at=expires_at,
            invitation_token=token,
        )


__all__ = [
    "AdministratorInvitationCommand",
    "AdministratorInvitationConflictError",
    "AdministratorInvitationDeniedError",
    "AdministratorInvitationReceipt",
    "AdministratorInvitationService",
]
