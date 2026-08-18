from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class SandboxApiKeyAuthority(Base):
    __tablename__ = "sandbox_api_key_authority"
    __table_args__ = (
        CheckConstraint("environment = 'sandbox'", name="environment"),
        CheckConstraint(
            "status IN ('enabled','revoked','expired','disabled')",
            name="status",
        ),
        CheckConstraint("usage_count >= 0", name="usage_count"),
        UniqueConstraint("key_hash", name="uq_sandbox_api_key_authority_hash"),
        Index(
            "ix_sandbox_api_key_authority_client_status",
            "client_ref",
            "status",
            "expires_at",
        ),
        Index(
            "ix_sandbox_api_key_authority_subscription",
            "subscription_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    key_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    client_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_user_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_id: Mapped[str] = mapped_column(String(128), nullable=False)
    operational_profile_id: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes_json: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    purpose: Mapped[str] = mapped_column(String(240), nullable=False)
    issued_to: Mapped[str] = mapped_column(String(128), nullable=False)
    issued_by_actor_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    environment: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="sandbox",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="enabled",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def scopes(self) -> list[str]:
        value = json.loads(self.scopes_json)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ValueError("Sandbox API-key scopes must be a JSON string list.")
        return value

    def mark_revoked(self, *, at: datetime | None = None) -> None:
        moment = at or datetime.now(UTC)
        self.status = "revoked"
        self.revoked_at = moment

    def mark_used(self, *, at: datetime | None = None) -> None:
        self.last_used_at = at or datetime.now(UTC)
        self.usage_count += 1


class SqlAlchemySandboxApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        key_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SandboxApiKeyAuthority | None:
        statement = select(SandboxApiKeyAuthority).where(
            SandboxApiKeyAuthority.id == key_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def list_active_for_client(
        self,
        client_ref: str,
    ) -> list[SandboxApiKeyAuthority]:
        now = datetime.now(UTC)
        statement = (
            select(SandboxApiKeyAuthority)
            .where(
                SandboxApiKeyAuthority.client_ref == client_ref,
                SandboxApiKeyAuthority.status == "enabled",
                SandboxApiKeyAuthority.revoked_at.is_(None),
                SandboxApiKeyAuthority.expires_at > now,
            )
            .order_by(SandboxApiKeyAuthority.created_at.desc())
        )
        return list((await self._session.scalars(statement)).all())

    async def candidates_by_prefix(
        self,
        key_prefix: str,
        *,
        for_update: bool = False,
    ) -> list[SandboxApiKeyAuthority]:
        statement = select(SandboxApiKeyAuthority).where(
            SandboxApiKeyAuthority.key_prefix == key_prefix,
            SandboxApiKeyAuthority.status == "enabled",
            SandboxApiKeyAuthority.revoked_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return list((await self._session.scalars(statement)).all())

    def add(self, key: SandboxApiKeyAuthority) -> None:
        self._session.add(key)
