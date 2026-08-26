from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class AdministratorInvitationDeliveryRepository(Protocol):
    async def invitation_by_id(self, *, invitation_id: uuid.UUID): ...


class AdministratorInvitationDeliveryDeniedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdministratorInvitationDeliveryGrant:
    invitation_id: uuid.UUID
    email_normalized: str
    supervision_level: str
    expires_at: datetime


class AdministratorInvitationDeliveryAuthority:
    def __init__(
        self,
        *,
        repository: AdministratorInvitationDeliveryRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Administrator invitation delivery clock must be timezone-aware.")
        return now

    @staticmethod
    def _deny() -> AdministratorInvitationDeliveryDeniedError:
        return AdministratorInvitationDeliveryDeniedError(
            "Administrator invitation delivery authority is invalid."
        )

    async def authorize(
        self,
        *,
        invitation_id: uuid.UUID,
        invitation_token: str,
    ) -> AdministratorInvitationDeliveryGrant:
        if not isinstance(invitation_token, str) or not invitation_token:
            raise self._deny()

        invitation = await self._repository.invitation_by_id(
            invitation_id=invitation_id
        )
        if invitation is None:
            raise self._deny()

        presented_hash = hashlib.sha256(
            invitation_token.encode("utf-8")
        ).hexdigest()
        stored_hash = str(invitation.token_hash)
        if not hmac.compare_digest(presented_hash, stored_hash):
            raise self._deny()

        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            raise self._deny()
        if (
            invitation.status != "pending"
            or invitation.accepted_by_user_id is not None
            or expires_at <= self._now()
        ):
            raise self._deny()

        return AdministratorInvitationDeliveryGrant(
            invitation_id=invitation.id,
            email_normalized=invitation.email_normalized,
            supervision_level=invitation.supervision_level,
            expires_at=expires_at,
        )


__all__ = [
    "AdministratorInvitationDeliveryAuthority",
    "AdministratorInvitationDeliveryDeniedError",
    "AdministratorInvitationDeliveryGrant",
]
