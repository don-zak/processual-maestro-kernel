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


class EvaluationGrantAuthority(Base):
    __tablename__ = "evaluation_grant_authority"
    __table_args__ = (
        CheckConstraint("max_requests > 0", name="max_requests"),
        CheckConstraint("used_requests >= 0", name="used_requests"),
        CheckConstraint("used_requests <= max_requests", name="quota_bound"),
        CheckConstraint("rejected_requests >= 0", name="rejected_requests"),
        CheckConstraint(
            "status IN ('active','revoked','expired','disabled')",
            name="status",
        ),
        UniqueConstraint("grant_ref", name="uq_evaluation_grant_authority_ref"),
        Index(
            "ix_evaluation_grant_authority_owner_status",
            "owner_user_ref",
            "status",
            "expires_at",
        ),
        Index(
            "ix_evaluation_grant_authority_client_status",
            "client_ref",
            "status",
            "expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    grant_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_user_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    client_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    user_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    issued_to: Mapped[str] = mapped_column(String(240), nullable=False)
    purpose: Mapped[str] = mapped_column(String(500), nullable=False)
    allowed_task_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    task_scope_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_scopes_json: Mapped[str] = mapped_column(Text, nullable=False)
    max_requests: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used_requests: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    rejected_requests: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    approved_by_actor_ref: Mapped[str] = mapped_column(String(240), nullable=False)
    approved_by_role: Mapped[str] = mapped_column(String(80), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @staticmethod
    def _string_list(raw: str) -> list[str]:
        value = json.loads(raw)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("evaluation authority list fields must contain JSON string lists")
        return value

    @property
    def allowed_task_ids(self) -> list[str]:
        return self._string_list(self.allowed_task_ids_json)

    @property
    def task_scope_ids(self) -> list[str]:
        return self._string_list(self.task_scope_ids_json)

    @property
    def allowed_scopes(self) -> list[str]:
        return self._string_list(self.allowed_scopes_json)

    def refresh_status(self, *, now: datetime | None = None) -> str:
        current = now or datetime.now(UTC)
        if self.status in {"revoked", "disabled"}:
            return self.status
        if self.expires_at <= current:
            self.status = "expired"
        return self.status


class EvaluationApiKeyAuthority(Base):
    __tablename__ = "evaluation_api_key_authority"
    __table_args__ = (
        CheckConstraint(
            "status IN ('enabled','revoked','expired','disabled')",
            name="status",
        ),
        CheckConstraint("usage_count >= 0", name="usage_count"),
        UniqueConstraint("key_ref", name="uq_evaluation_api_key_authority_ref"),
        UniqueConstraint("key_hash", name="uq_evaluation_api_key_authority_hash"),
        Index(
            "ix_evaluation_api_key_authority_grant_status",
            "grant_id",
            "status",
            "expires_at",
        ),
        Index("ix_evaluation_api_key_authority_prefix", "key_prefix"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    grant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_grant_authority.id", ondelete="RESTRICT"),
        nullable=False,
    )
    key_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    client_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    user_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    scopes_json: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_task_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    task_scope_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def scopes(self) -> list[str]:
        return EvaluationGrantAuthority._string_list(self.scopes_json)

    @property
    def allowed_task_ids(self) -> list[str]:
        return EvaluationGrantAuthority._string_list(self.allowed_task_ids_json)

    @property
    def task_scope_ids(self) -> list[str]:
        return EvaluationGrantAuthority._string_list(self.task_scope_ids_json)


class EvaluationUsageLedger(Base):
    __tablename__ = "evaluation_usage_ledger"
    __table_args__ = (
        CheckConstraint("units > 0", name="units"),
        UniqueConstraint(
            "grant_id",
            "idempotency_key",
            name="uq_evaluation_usage_ledger_idempotency",
        ),
        Index(
            "ix_evaluation_usage_ledger_grant_created",
            "grant_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    grant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_grant_authority.id", ondelete="RESTRICT"),
        nullable=False,
    )
    key_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_api_key_authority.id", ondelete="RESTRICT"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    task_id: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SqlAlchemyEvaluationAuthorityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_grant_by_id(
        self,
        grant_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> EvaluationGrantAuthority | None:
        statement = select(EvaluationGrantAuthority).where(
            EvaluationGrantAuthority.id == grant_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_grant_by_ref(
        self,
        grant_ref: str,
        *,
        for_update: bool = False,
    ) -> EvaluationGrantAuthority | None:
        statement = select(EvaluationGrantAuthority).where(
            EvaluationGrantAuthority.grant_ref == grant_ref
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_key_by_id(
        self,
        key_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> EvaluationApiKeyAuthority | None:
        statement = select(EvaluationApiKeyAuthority).where(
            EvaluationApiKeyAuthority.id == key_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def list_grants_for_owner(self, owner_user_ref: str) -> list[EvaluationGrantAuthority]:
        statement = (
            select(EvaluationGrantAuthority)
            .where(EvaluationGrantAuthority.owner_user_ref == owner_user_ref)
            .order_by(EvaluationGrantAuthority.created_at.desc())
        )
        return list((await self._session.scalars(statement)).all())

    async def active_keys_for_grant(
        self,
        grant_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> list[EvaluationApiKeyAuthority]:
        now = datetime.now(UTC)
        statement = (
            select(EvaluationApiKeyAuthority)
            .where(
                EvaluationApiKeyAuthority.grant_id == grant_id,
                EvaluationApiKeyAuthority.status == "enabled",
                EvaluationApiKeyAuthority.revoked_at.is_(None),
                EvaluationApiKeyAuthority.expires_at > now,
            )
            .order_by(EvaluationApiKeyAuthority.created_at.asc())
        )
        if for_update:
            statement = statement.with_for_update()
        return list((await self._session.scalars(statement)).all())

    async def key_candidates_by_prefix(
        self,
        key_prefix: str,
        *,
        for_update: bool = False,
    ) -> list[EvaluationApiKeyAuthority]:
        statement = select(EvaluationApiKeyAuthority).where(
            EvaluationApiKeyAuthority.key_prefix == key_prefix
        )
        if for_update:
            statement = statement.with_for_update()
        return list((await self._session.scalars(statement)).all())

    async def usage_by_idempotency(
        self,
        grant_id: uuid.UUID,
        idempotency_key: str,
    ) -> EvaluationUsageLedger | None:
        return await self._session.scalar(
            select(EvaluationUsageLedger).where(
                EvaluationUsageLedger.grant_id == grant_id,
                EvaluationUsageLedger.idempotency_key == idempotency_key,
            )
        )

    def add(self, record: Base) -> None:
        self._session.add(record)


__all__ = [
    "EvaluationApiKeyAuthority",
    "EvaluationGrantAuthority",
    "EvaluationUsageLedger",
    "SqlAlchemyEvaluationAuthorityRepository",
]
