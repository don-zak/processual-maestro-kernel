from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from processual_api.admin_governance.permission_authority import (
    AdministratorGovernanceAction,
    AdministratorGovernanceAuthorityContext,
    evaluate_administrator_governance_authority,
)


class AdministratorLifecycleRepository(Protocol):
    async def administrator_for_update(self, *, user_id: uuid.UUID): ...
    async def platform_supervisor_for_update(self, *, user_id: uuid.UUID): ...
    async def administrator_session_for_update(
        self,
        *,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ): ...

    async def revoke_session(
        self,
        *,
        session,
        revoked_at: datetime,
        reason: str,
    ) -> None: ...

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


class AdministratorLifecycleUnitOfWork(Protocol):
    repository: AdministratorLifecycleRepository

    async def __aenter__(self): ...
    async def __aexit__(self, exc_type, exc, traceback): ...
    async def commit(self) -> None: ...


class AdministratorLifecycleDeniedError(RuntimeError):
    pass


class AdministratorLifecycleConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdministratorLifecycleReceipt:
    user_id: uuid.UUID
    status: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class AdministratorSessionRevocationReceipt:
    user_id: uuid.UUID
    session_id: uuid.UUID
    revoked_at: datetime


class AdministratorLifecycleService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdministratorLifecycleUnitOfWork],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Administrator lifecycle clock must be timezone-aware.")
        return now

    @staticmethod
    def _normalize_reason(value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 12 or len(normalized) > 500:
            raise ValueError("Administrator lifecycle reason is invalid.")
        return normalized

    @staticmethod
    def _authorize(
        *,
        context: AdministratorGovernanceAuthorityContext,
        action: AdministratorGovernanceAction,
    ) -> None:
        decision = evaluate_administrator_governance_authority(
            context=context,
            action=action,
        )
        if not decision.allowed:
            raise AdministratorLifecycleDeniedError(decision.reason_code)

    async def revoke_session(
        self,
        *,
        target_user_id: uuid.UUID,
        session_id: uuid.UUID,
        authority_context: AdministratorGovernanceAuthorityContext,
        reason: str,
    ) -> AdministratorSessionRevocationReceipt:
        self._authorize(
            context=authority_context,
            action=AdministratorGovernanceAction.REVOKE_SESSION,
        )
        actor_user_id = uuid.UUID(authority_context.user_id)
        normalized_reason = self._normalize_reason(reason)
        now = self._now()

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            user = await repository.administrator_for_update(user_id=target_user_id)
            authority = await repository.platform_supervisor_for_update(
                user_id=target_user_id
            )
            if user is None or authority is None or authority.status != "active":
                raise AdministratorLifecycleConflictError(
                    "Administrator is not an active platform supervisor."
                )
            if user.status != "active":
                raise AdministratorLifecycleConflictError(
                    "Administrator is not in an active state."
                )

            session = await repository.administrator_session_for_update(
                session_id=session_id,
                user_id=target_user_id,
            )
            if session is None or session.revoked_at is not None or session.expires_at <= now:
                raise AdministratorLifecycleConflictError(
                    "Administrator session is not revocable."
                )

            await repository.revoke_session(
                session=session,
                revoked_at=now,
                reason="administrator_session_revoked",
            )
            repository.add_governance_audit_event(
                event_type="administrator_session_revoked",
                actor_user_id=actor_user_id,
                subject_user_id=target_user_id,
                invitation_id=None,
                permission=AdministratorGovernanceAction.REVOKE_SESSION.value,
                reason=normalized_reason,
                occurred_at=now,
            )
            await unit.commit()

        return AdministratorSessionRevocationReceipt(
            user_id=target_user_id,
            session_id=session_id,
            revoked_at=now,
        )

    async def freeze(
        self,
        *,
        target_user_id: uuid.UUID,
        authority_context: AdministratorGovernanceAuthorityContext,
        reason: str,
    ) -> AdministratorLifecycleReceipt:
        self._authorize(
            context=authority_context,
            action=AdministratorGovernanceAction.FREEZE_ADMINISTRATOR,
        )
        actor_user_id = uuid.UUID(authority_context.user_id)
        if actor_user_id == target_user_id:
            raise AdministratorLifecycleDeniedError("self_freeze_denied")

        normalized_reason = self._normalize_reason(reason)
        now = self._now()

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            user = await repository.administrator_for_update(user_id=target_user_id)
            authority = await repository.platform_supervisor_for_update(
                user_id=target_user_id
            )
            if user is None or authority is None or authority.status != "active":
                raise AdministratorLifecycleConflictError(
                    "Administrator is not an active platform supervisor."
                )
            if user.status != "active":
                raise AdministratorLifecycleConflictError(
                    "Administrator is not in an active state."
                )

            user.status = "locked"
            user.updated_at = now
            await repository.revoke_all_sessions(
                user_id=target_user_id,
                revoked_at=now,
                reason="administrator_frozen",
            )
            repository.add_governance_audit_event(
                event_type="administrator_frozen",
                actor_user_id=actor_user_id,
                subject_user_id=target_user_id,
                invitation_id=None,
                permission=AdministratorGovernanceAction.FREEZE_ADMINISTRATOR.value,
                reason=normalized_reason,
                occurred_at=now,
            )
            await unit.commit()

        return AdministratorLifecycleReceipt(
            user_id=target_user_id,
            status="locked",
            occurred_at=now,
        )

    async def restore(
        self,
        *,
        target_user_id: uuid.UUID,
        authority_context: AdministratorGovernanceAuthorityContext,
        reason: str,
    ) -> AdministratorLifecycleReceipt:
        self._authorize(
            context=authority_context,
            action=AdministratorGovernanceAction.RESTORE_ADMINISTRATOR,
        )
        actor_user_id = uuid.UUID(authority_context.user_id)
        normalized_reason = self._normalize_reason(reason)
        now = self._now()

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            user = await repository.administrator_for_update(user_id=target_user_id)
            authority = await repository.platform_supervisor_for_update(
                user_id=target_user_id
            )
            if user is None or authority is None or authority.status != "active":
                raise AdministratorLifecycleConflictError(
                    "Administrator is not an active platform supervisor."
                )
            if user.status != "locked":
                raise AdministratorLifecycleConflictError(
                    "Administrator is not frozen."
                )

            user.status = "active"
            user.updated_at = now
            repository.add_governance_audit_event(
                event_type="administrator_restored",
                actor_user_id=actor_user_id,
                subject_user_id=target_user_id,
                invitation_id=None,
                permission=AdministratorGovernanceAction.RESTORE_ADMINISTRATOR.value,
                reason=normalized_reason,
                occurred_at=now,
            )
            await unit.commit()

        return AdministratorLifecycleReceipt(
            user_id=target_user_id,
            status="active",
            occurred_at=now,
        )


__all__ = [
    "AdministratorLifecycleConflictError",
    "AdministratorLifecycleDeniedError",
    "AdministratorLifecycleReceipt",
    "AdministratorLifecycleService",
    "AdministratorSessionRevocationReceipt",
]
