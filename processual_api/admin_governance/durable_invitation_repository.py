from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_governance.invitation_repository import (
    SqlAlchemyAdministratorInvitationRepository,
)
from processual_api.admin_governance.models import (
    AdministratorInvitationDeliveryOutbox,
)


class SqlAlchemyDurableAdministratorInvitationRepository(
    SqlAlchemyAdministratorInvitationRepository
):
    def add_invitation_delivery_outbox(
        self,
        *,
        outbox_id: uuid.UUID,
        invitation_id: uuid.UUID,
        recipient_email_normalized: str,
        event_type: str,
        payload_ciphertext: bytes,
        payload_key_version: str,
        idempotency_key: str,
        status: str,
        attempts: int,
        next_attempt_at: datetime,
        created_at: datetime,
    ) -> AdministratorInvitationDeliveryOutbox:
        row = AdministratorInvitationDeliveryOutbox(
            id=outbox_id,
            invitation_id=invitation_id,
            recipient_email_normalized=recipient_email_normalized,
            event_type=event_type,
            payload_ciphertext=payload_ciphertext,
            payload_key_version=payload_key_version,
            idempotency_key=idempotency_key,
            status=status,
            attempts=attempts,
            next_attempt_at=next_attempt_at,
            created_at=created_at,
            updated_at=created_at,
        )
        self._session.add(row)
        return row


class SqlAlchemyDurableAdministratorInvitationUnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.repository: SqlAlchemyDurableAdministratorInvitationRepository | None = None
        self._committed = False

    async def __aenter__(self):
        self._session = self._session_factory()
        self.repository = SqlAlchemyDurableAdministratorInvitationRepository(self._session)
        return self

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Durable administrator invitation unit of work is not active.")
        await self._session.commit()
        self._committed = True

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._session is None:
            return
        if exc is not None or not self._committed:
            await self._session.rollback()
        await self._session.close()


__all__ = [
    "SqlAlchemyDurableAdministratorInvitationRepository",
    "SqlAlchemyDurableAdministratorInvitationUnitOfWork",
]
