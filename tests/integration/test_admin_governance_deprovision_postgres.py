from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_governance.administrator_deprovision_repository import (
    SqlAlchemyAdministratorDeprovisionUnitOfWork,
)
from processual_api.admin_governance.administrator_deprovision_service import (
    AdministratorDeprovisionService,
)
from processual_api.admin_governance.administrator_governance_history import (
    AdministratorGovernanceHistoryService,
)
from processual_api.admin_governance.models import (
    AdministratorGovernanceAuditEvent,
    AdministratorInvitation,
    AdministratorPermissionGrant,
)
from processual_api.auth.models import (
    AuthRefreshToken,
    AuthSession,
    IdentityPlatformAuthority,
    IdentityUser,
)

DATABASE_URL = os.environ.get("ADMIN_GOVERNANCE_INTEGRATION_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="Set ADMIN_GOVERNANCE_INTEGRATION_DATABASE_URL to run the governance gate.",
)

NOW = datetime(2026, 8, 23, 5, 0, tzinfo=UTC)


def _async_database_url() -> str:
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        return DATABASE_URL
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.mark.asyncio
async def test_supervisor_deprovision_revokes_authority_grants_and_sessions_atomically() -> None:
    engine = create_async_engine(_async_database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    suffix = uuid.uuid4().hex
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()
    invitation_id = uuid.uuid4()
    authority_id = uuid.uuid4()
    grant_id = uuid.uuid4()
    session_id = uuid.uuid4()
    refresh_id = uuid.uuid4()
    family_id = uuid.uuid4()
    reason = "Supervisor access is no longer operationally required."

    try:
        async with session_factory() as session:
            actor = IdentityUser(
                id=actor_id,
                email_normalized=f"gov-admin-{suffix}@example.test",
                display_name="Governance Admin",
                password_hash="integration-only",
                status="active",
                email_verified_at=NOW,
            )
            target = IdentityUser(
                id=target_id,
                email_normalized=f"gov-supervisor-{suffix}@example.test",
                display_name="Governance Supervisor",
                password_hash="integration-only",
                status="active",
                email_verified_at=NOW,
            )
            session.add_all([actor, target])
            await session.flush()

            session.add(
                IdentityPlatformAuthority(
                    user_id=actor_id,
                    authority="platform_admin",
                    status="active",
                    granted_by_user_id=None,
                    grant_reason="Integration authority seed",
                    granted_at=NOW,
                )
            )
            invitation = AdministratorInvitation(
                id=invitation_id,
                email_normalized=target.email_normalized,
                supervision_level="operations_supervisor",
                token_hash=uuid.uuid4().hex + uuid.uuid4().hex,
                status="accepted",
                invited_by_user_id=actor_id,
                invite_reason="Integration supervisor authority seed",
                expires_at=NOW + timedelta(days=1),
                accepted_by_user_id=target_id,
                accepted_at=NOW,
            )
            session.add(invitation)
            await session.flush()

            session.add(
                IdentityPlatformAuthority(
                    id=authority_id,
                    user_id=target_id,
                    authority="platform_supervisor",
                    status="active",
                    granted_by_user_id=actor_id,
                    grant_reason="Integration supervisor authority seed",
                    granted_at=NOW,
                )
            )
            session.add(
                AdministratorPermissionGrant(
                    id=grant_id,
                    user_id=target_id,
                    permission="governance.activity.view",
                    status="active",
                    source_invitation_id=invitation_id,
                    granted_by_user_id=actor_id,
                    grant_reason="Integration supervisor permission seed",
                    granted_at=NOW,
                )
            )
            auth_session = AuthSession(
                id=session_id,
                user_id=target_id,
                refresh_family_id=family_id,
                authenticated_at=NOW,
                mfa_satisfied_at=NOW,
                last_seen_at=NOW,
                expires_at=NOW + timedelta(hours=4),
            )
            session.add(auth_session)
            await session.flush()
            session.add(
                AuthRefreshToken(
                    id=refresh_id,
                    session_id=session_id,
                    token_hash=uuid.uuid4().hex + uuid.uuid4().hex,
                    issued_at=NOW,
                    expires_at=NOW + timedelta(hours=4),
                )
            )
            await session.commit()

        service = AdministratorDeprovisionService(
            unit_of_work_factory=lambda: SqlAlchemyAdministratorDeprovisionUnitOfWork(
                session_factory
            ),
            clock=lambda: NOW,
        )
        receipt = await service.revoke_supervisor_authority(
            actor_user_id=actor_id,
            target_user_id=target_id,
            reason=reason,
            recent_step_up=True,
        )

        assert receipt.status == "revoked"
        assert receipt.revoked_permission_count == 1

        async with session_factory() as session:
            authority = await session.scalar(
                select(IdentityPlatformAuthority).where(
                    IdentityPlatformAuthority.id == authority_id
                )
            )
            grant = await session.scalar(
                select(AdministratorPermissionGrant).where(
                    AdministratorPermissionGrant.id == grant_id
                )
            )
            auth_session = await session.scalar(
                select(AuthSession).where(AuthSession.id == session_id)
            )
            refresh = await session.scalar(
                select(AuthRefreshToken).where(AuthRefreshToken.id == refresh_id)
            )
            events = tuple(
                (
                    await session.scalars(
                        select(AdministratorGovernanceAuditEvent)
                        .where(AdministratorGovernanceAuditEvent.subject_user_id == target_id)
                        .order_by(AdministratorGovernanceAuditEvent.occurred_at.asc())
                    )
                ).all()
            )

            assert authority is not None
            assert authority.status == "revoked"
            assert authority.revoked_by_user_id == actor_id
            assert authority.revoke_reason == reason
            assert authority.revoked_at == NOW
            assert grant is not None
            assert grant.status == "revoked"
            assert grant.revoked_by_user_id == actor_id
            assert grant.revocation_reason == reason
            assert grant.revoked_at == NOW
            assert auth_session is not None
            assert auth_session.revoked_at == NOW
            assert auth_session.revoke_reason == "administrator_supervisor_authority_revoked"
            assert refresh is not None
            assert refresh.revoked_at == NOW
            assert [event.event_type for event in events] == [
                "administrator.permission.revoked",
                "administrator.supervisor_authority.revoked",
            ]

        history = await AdministratorGovernanceHistoryService(
            session_factory=session_factory
        ).get_history(user_id=target_id)
        assert history is not None
        assert history.user_id == target_id
        assert len(history.authorities) == 1
        assert history.authorities[0].authority == "platform_supervisor"
        assert history.authorities[0].status == "revoked"
        assert history.authorities[0].revoked_by_user_id == actor_id
        assert history.authorities[0].revoke_reason == reason
        assert len(history.permissions) == 1
        assert history.permissions[0].permission == "governance.activity.view"
        assert history.permissions[0].status == "revoked"
        assert history.permissions[0].source_invitation_id == invitation_id
        assert history.permissions[0].revoked_by_user_id == actor_id
        assert history.permissions[0].revocation_reason == reason
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(AdministratorGovernanceAuditEvent).where(
                    AdministratorGovernanceAuditEvent.subject_user_id == target_id
                )
            )
            await session.execute(
                delete(AuthRefreshToken).where(AuthRefreshToken.id == refresh_id)
            )
            await session.execute(delete(AuthSession).where(AuthSession.id == session_id))
            await session.execute(
                delete(AdministratorPermissionGrant).where(
                    AdministratorPermissionGrant.id == grant_id
                )
            )
            await session.execute(
                delete(IdentityPlatformAuthority).where(
                    IdentityPlatformAuthority.user_id.in_([actor_id, target_id])
                )
            )
            await session.execute(
                delete(AdministratorInvitation).where(
                    AdministratorInvitation.id == invitation_id
                )
            )
            await session.execute(
                delete(IdentityUser).where(IdentityUser.id.in_([actor_id, target_id]))
            )
            await session.commit()
        await engine.dispose()
