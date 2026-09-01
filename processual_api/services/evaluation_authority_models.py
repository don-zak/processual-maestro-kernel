from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class EvaluationAuthorityState(Base):
    __tablename__ = "evaluation_authority_state"

    owner_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    authority: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    production_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    raw_secret_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())


class EvaluationAuthorityKey(Base):
    __tablename__ = "evaluation_authority_key"

    key_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        String(200),
        ForeignKey("evaluation_authority_state.owner_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    grant_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    lookup_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    prefix: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    hashed: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="enabled")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quota_rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    production_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    raw_secret_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())


__all__ = ["EvaluationAuthorityKey", "EvaluationAuthorityState"]
