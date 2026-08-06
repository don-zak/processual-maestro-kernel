from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdminMarketLemonSqueezyCustomerBinding(Base):
    __tablename__ = "admin_market_lemon_squeezy_customer_bindings"
    __table_args__ = (
        UniqueConstraint(
            "customer_ref",
            name="uq_admin_market_ls_customer_binding_customer",
        ),
        UniqueConstraint(
            "provider_customer_id",
            name="uq_admin_market_ls_customer_binding_provider_customer",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(128), nullable=False)
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


class AdminMarketLemonSqueezyBinding(Base):
    __tablename__ = "admin_market_lemon_squeezy_bindings"
    __table_args__ = (
        CheckConstraint("length(currency) = 3", name="currency_length"),
        UniqueConstraint("order_id", name="uq_admin_market_ls_binding_order"),
        UniqueConstraint(
            "provider_order_id",
            name="uq_admin_market_ls_binding_provider_order",
        ),
        UniqueConstraint(
            "provider_subscription_id",
            name="uq_admin_market_ls_binding_provider_subscription",
        ),
        Index(
            "ix_admin_market_ls_binding_customer",
            "customer_ref",
            "last_provider_effective_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_ref: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "admin_market_lemon_squeezy_customer_bindings.customer_ref",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_offers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_subscriptions.id", ondelete="RESTRICT"),
    )
    provider_customer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(128))
    variant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount: Mapped[str] = mapped_column(String(64), nullable=False)
    last_provider_effective_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
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


class SqlAlchemyLemonSqueezyBindingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_customer_binding_by_customer_ref(
        self,
        customer_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketLemonSqueezyCustomerBinding | None:
        statement = select(AdminMarketLemonSqueezyCustomerBinding).where(
            AdminMarketLemonSqueezyCustomerBinding.customer_ref == customer_ref
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_customer_binding_by_provider_customer_id(
        self,
        provider_customer_id: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketLemonSqueezyCustomerBinding | None:
        statement = select(AdminMarketLemonSqueezyCustomerBinding).where(
            AdminMarketLemonSqueezyCustomerBinding.provider_customer_id
            == provider_customer_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_order_id(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketLemonSqueezyBinding | None:
        statement = select(AdminMarketLemonSqueezyBinding).where(
            AdminMarketLemonSqueezyBinding.order_id == order_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_provider_subscription_id(
        self,
        provider_subscription_id: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketLemonSqueezyBinding | None:
        statement = select(AdminMarketLemonSqueezyBinding).where(
            AdminMarketLemonSqueezyBinding.provider_subscription_id
            == provider_subscription_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add_customer_binding(
        self,
        binding: AdminMarketLemonSqueezyCustomerBinding,
    ) -> None:
        self._session.add(binding)

    def add(self, binding: AdminMarketLemonSqueezyBinding) -> None:
        self._session.add(binding)


__all__ = [
    "AdminMarketLemonSqueezyBinding",
    "AdminMarketLemonSqueezyCustomerBinding",
    "SqlAlchemyLemonSqueezyBindingRepository",
]
