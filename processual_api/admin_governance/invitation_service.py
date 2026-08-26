from __future__ import annotations

import hashlib
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from processual_api.admin_governance.invitation_delivery_crypto import (
    AdministratorInvitationPayloadCipher,
)
from processual_api.auth.normalization import normalize_email


class AdministratorInvitationRepository(Protocol):
    async def active_platform_admin(self, *, user_id: uuid.UUID): ...
    async def active_invitation_for_email(self, *, email_normalized: str): ...
    async def identity_exists(self, *, email_normalized: str) -> bool: ...
    def add_invitation(self, **values): ...
    def add_invitation_delivery_outbox(self, **values): ...
    def add_governance_audit_event(self, **values): ...


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
    delivery_outbox_id: uuid.UUID
    email_normalized: str
    supervision_level: str
    expires_at: datetime
    invitation_token: str


class AdministratorInvitationService:
    _ALLOWED_LEVELS = frozenset({"operations_supervisor", "review_supervisor"})

    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdministratorInvitationUnitOfWork],
        payload_cipher: AdministratorInvitationPayloadCipher,
        clock: Callable[[], datetime] | None = None,
        invitation_id_factory: Callable[[], uuid.UUID] | None = None,
        outbox_id_factory: Callable[[], uuid.UUID] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._payload_cipher = payload_cipher
        self._clock = clock or (lambda: datetime.now(UTC))
        self._invitation_id_factory = invitation_id_factory or uuid.uuid4
        self._outbox_id_factory = outbox_id_factory or uuid.uuid4

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
        outbox_id = self._outbox_id_factory()
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        encrypted = self._payload_cipher.encrypt(
            token,
            outbox_id=str(outbox_id),
            invitation_id=str(invitation_id),
            recipient_email=email_normalized,
        )
        idempotency_key = f"pmk-admin-governance-invitation-v2:{invitation_id}"

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
            repository.add_invitation_delivery_outbox(
                outbox_id=outbox_id,
                invitation_id=invitation_id,
                recipient_email_normalized=email_normalized,
                event_type="admin_governance_invitation",
                payload_ciphertext=encrypted.ciphertext,
                payload_key_version=encrypted.key_version,
                idempotency_key=idempotency_key,
                status="pending",
                attempts=0,
                next_attempt_at=now,
                created_at=now,
            )
            repository.add_governance_audit_event(
                event_type="administrator_invitation_issued",
                actor_user_id=actor_user_id,
                subject_user_id=None,
                invitation_id=invitation_id,
                permission=None,
                reason=reason,
                occurred_at=now,
            )
            await unit.commit()

        return AdministratorInvitationReceipt(
            invitation_id=invitation_id,
            delivery_outbox_id=outbox_id,
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
